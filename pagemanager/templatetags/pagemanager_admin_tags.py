from django import template
from django.contrib.admin.sites import site
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.text import capfirst

from pagemanager.app_settings import PAGEMANAGER_PAGE_MODEL
from pagemanager.permissions import get_permissions, get_lookup_function
from pagemanager.util import get_pagemanager_model

register = template.Library()


class NavListNode(template.Node):

    def render(self, context):
        if 'navigation' in settings.INSTALLED_APPS:
            return render_to_string('pagemanager/admin/navigation.html')
        else:
            return ''


@register.tag
def render_navigation_list(parser, token):
    """
    In any admin change_view, adds the object being changed to the context
    """
    return NavListNode()


class ObjNode(template.Node):

    def render(self, context):

        layout_ct = ContentType.objects.get_for_id(context['content_type_id'])
        layout_class = layout_ct.model_class()

        context['obj'] = layout_class.objects.get(pk=int(context['object_id']))
        context['page'] = context['obj'].page.all()[0]

        return ''

@register.tag
def load_obj(parser, token):
    """
    In any admin change_view, adds the object being changed to the context
    """
    return ObjNode()


class PagesNode(template.Node):
    def render(self, context):
        context['pagemanager_pages'] = PAGEMANAGER_PAGE_MODEL.objects.all()
        context['pagemanager_page_model'] = PAGEMANAGER_PAGE_MODEL
        return ''

@register.tag
def load_pages(parser, token):
    """
    In any admin change_view, adds the object being changed to the context
    """
    return PagesNode()


class AppListNode(template.Node):

    def render(self, context):

        if 'django.core.context_processors.request' not in \
            settings.TEMPLATE_CONTEXT_PROCESSORS:
            raise ImproperlyConfigured(
                'The TEMPLATE_CONTEXT_PROCESSORS setting must contain '
                'django.core.context_processors.request'
            )

        app_dict = {}
        request = context['request']
        user = request.user
        for model, model_admin in site._registry.items():

            # Try to retrieve the __admin_name__ property from the
            # model's app's __init__.py
            to_import = '.'.join(model.__module__.split('.')[:-1])
            try:
                app_label = __import__(to_import).__APP_NAME__
            except AttributeError:
                app_label = model._meta.app_label.title()
            app_url = model._meta.app_label.lower()

            has_module_perms = user.has_module_perms(
                model._meta.app_label.lower()
            )
            hidden_model = hasattr(model, 'hide_from_applist') and \
                model.hide_from_applist()
            if has_module_perms and not hidden_model:
                perms = model_admin.get_model_perms(request)
                if True in perms.values():

                    model_dict = {
                        'name': capfirst(model._meta.verbose_name_plural),
                        'admin_url': mark_safe('%s/%s/' % (
                            app_url, 
                            model.__name__.lower())
                        ),
                        'perms': perms,
                    }
                    if app_label in app_dict:
                        app_dict[app_label]['models'].append(model_dict)
                    else:
                        app_dict[app_label] = {
                            'name': app_label,
                            'app_url': app_url + '/',
                            'has_module_perms': has_module_perms,
                            'models': [model_dict],
                        }

        # Sort the apps alphabetically, then sort models alphabetically within
        # each app
        app_list = app_dict.values()
        app_list.sort(key=lambda x: x['name'])
        for app in app_list:
            app['models'].sort(key=lambda x: x['name'])

        context['app_list'] = app_list
        return ''

@register.tag
def pagemanager_app_list(parser, token):
    """

    """
    return AppListNode()


class LookupPermissionsNode(template.Node):
    """
    A template tag rederer that provides info about the types of permissions
    the given user has on the given node.
    """
    def __init__(self, node_var_name, user_var_name):
        self.node_var = template.Variable(node_var_name)
        self.user_var = template.Variable(user_var_name)

    @staticmethod
    def _rename_permissions(permissions_dict, model_name):
        """
        This function is used to ensure that the variable names created in
        the template context are standardized. We deal with permissions that
        have the name of the model in them, but model name may change. We want
        to have the context variable names always be the same, even though they
        are generated from the actual permission names. Therefore we replace
        any appearance of the model name or "page" with "object".
        """
        for permission_name, permission in permissions_dict.items():
            new_name = permission_name.replace(
                model_name, "object"
            ).replace(
                "page", "object"
            )
            if new_name != permission_name:
                permissions_dict[new_name] = permission
                del permissions_dict[permission_name]
        return permissions_dict

    def render(self, context):
        permission_names = get_permissions()
        permissions = dict([(k, False) for k in permission_names.keys()])

        # Adding shortcut permission that combines ``view_private_pages`` and
        # `` view_draft_pages`` permissions.
        permissions['view_page'] = False
        try:
            user = self.user_var.resolve(context)
        except template.VariableDoesNotExist:
            # If user variable can't be resolved, all permissions are False.
            permissions = self._rename_permissions(permissions, "page")
            for permission_name, permission in permissions.items():
                context[permission_name] = permission
            return ''
        # If node variable can't be resolved, some permissions can still
        # be useful.
        try:
            node = self.node_var.resolve(context)
        except template.VariableDoesNotExist:
            node = None
            opts = get_pagemanager_model()._meta
        else:
            opts = node.__class__._meta

        lookup_perm = get_lookup_function(user,permission_names)

        # Shortcut: if the user is a superuser we can just set all permissions
        # to True and be done with it.
        if user.is_superuser:
            permissions = self._rename_permissions(
                permissions, opts.module_name
            )
            for permission_name, permission in permissions.items():
                context[permission_name] = True
            return ''

        # Determine visibility permissions.
        if node:
            if not node.is_visible() and lookup_perm('view_private_pages'):
                permissions['view_private_pages'] = True
            if not node.is_published() and lookup_perm('view_draft_pages'):
                permissions['view_draft_pages'] = True
            if (node.is_visible() or permissions['view_private_pages']) and \
                (node.is_published() or permissions['view_draft_pages']):
                permissions['view_page'] = True

        # Determine standard model permissions.
        for verb in ('add', 'change', 'delete'):
            permission_name = "%s_%s" % (verb, opts.module_name)
            if lookup_perm(permission_name):
                permissions[permission_name] = True
        # Commit all permissions to context:
        permissions = self._rename_permissions(permissions, opts.module_name)
        for permission_name, permission in permissions.items():
            context[permission_name] = permission
        return ''

@register.tag
def lookup_permissions(parser, token):
    """
    A template tag node that provides info about the types of permissions
    the given user has on the given node. Example usage:

        {% lookup_permissions node user %}

    This sets the following boolean variables in the template context:

        'add_object'
        'delete_object'
        'change_object'
        'view_draft_objects'
        'view_private_objects'
        'view_object'
        'change_visibility'
        'change_status'
        'modify_published_objects'

    """
    try:
        tag_name, node_var_name, user_var_name = token.split_contents()
    except ValueError:
        message = (
            "The lookup_permissions tag requires a two arguments: "
            " the node to find permissions for and the user."
        )
        raise template.TemplateSyntaxError, message

    return LookupPermissionsNode(node_var_name, user_var_name)
