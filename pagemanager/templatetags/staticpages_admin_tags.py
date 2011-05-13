from django import template
from django.contrib.admin.sites import AdminSite, site
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from django.utils.text import capfirst

from pagemanager.app_settings import STATICPAGES_PAGE_MODEL

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
        context['staticpages_pages'] = STATICPAGES_PAGE_MODEL.objects.all()
        context['staticpages_page_model'] = STATICPAGES_PAGE_MODEL
        return ''

@register.tag
def load_pages(parser, token):
    """
    In any admin change_view, adds the object being changed to the context
    """
    return PagesNode()


class AppListNode(template.Node):

    def render(self, context):
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
def staticpages_app_list(parser, token):
    """

    """
    return AppListNode()
