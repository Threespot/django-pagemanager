from django import template
from django.contrib.admin.sites import AdminSite, site
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.safestring import mark_safe
from django.utils.text import capfirst

from pagemanager.app_settings import PAGEMANAGER_PAGE_MODEL

register = template.Library()


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
            app_label = model._meta.app_label
            has_module_perms = user.has_module_perms(app_label)
            hidden_model = hasattr(model, 'hide_from_applist') and \
                model.hide_from_applist()
            if has_module_perms and not hidden_model:
                perms = model_admin.get_model_perms(request)
                if True in perms.values():
                    model_dict = {
                        'name': capfirst(model._meta.verbose_name_plural),
                        'admin_url': mark_safe('%s/%s/' % (app_label, model.__name__.lower())),
                        'perms': perms,
                    }
                    if app_label in app_dict:
                        app_dict[app_label]['models'].append(model_dict)
                    else:
                        app_dict[app_label] = {
                            'name': app_label.title(),
                            'app_url': app_label + '/',
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
    
    def __init__(self, node_var_name, user_var_name):
        self.node_var = template.Variable(node_var_name)
        self.user_var = template.Variable(user_var_name)
    
    def render(self, context):
        permissions = {
            'can_view_node': False,
            'can_add_node': False,
            'can_edit_node': False,
            'can_delete_node': False
        }
        try:
            node = self.node_var.resolve(context)
            user = self.user_var.resolve(context)
        except:
            for perm_name, perm in permissions.items():
                context[perm_name] = perm
            return ''
        
        # Determine 'can_view' pmerissions.
        opts = node.__class__._meta
        user_permissions = user.get_all_permissions()
        view_priv_perm = "%s.can_view_private_pages" % opts.app_label
        view_unpub_perm = "%s.can_view_draft_pages" % opts.app_label
        if not node.is_visible:
            if user.has_perm(view_priv_perm):
                permissions['can_view_node'] = True
        elif not node.is_published:
            if user.has_perm(view_unpub_perm):
                permissions['can_view_node'] = True
        else:
            # Node is not private or draft, so everyone can see it.
            permissions['can_view_node'] = True
        # Determine 'can_add_node' permissions.
        if user.has_perm("%s.add_%s" % (opts.app_label, opts.module_name)):
            permissions['can_add_node'] = True
        # Determine 'can_edit' permissions.
        if user.has_perm("%s.change_%s" % (opts.app_label, opts.module_name)):
            permissions['can_edit_node'] = True
        # Determine 'can_delete' permissions.
        if user.has_perm("%s.delete_%s" % (opts.app_label, opts.module_name)):
            permissions['can_delete_node'] = True
        
        for perm_name, perm in permissions.items():
            context[perm_name] = perm
        return ''

@register.tag
def lookup_permissions(parser, token):
    try:
        tag_name, node_var_name, user_var_name = token.split_contents()
    except ValueError:
        message = (
            "The lookup_permissions tag requires a two arguments: "
            " the node to find permissions for and the user."
        )
        raise template.TemplateSyntaxError, message
    
    return LookupPermissionsNode(node_var_name, user_var_name)