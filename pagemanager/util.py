from functools import partial

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.http import Http404

from pagemanager import PageAdmin
from pagemanager.models import Page


def get_pagemanager_model():
    """
    Returns the model to be used by pagemanager. It must be either
    pagemanager.models.Page or a subclass thereof.
    """
    if hasattr(settings, 'PAGEMANAGER_PAGE_MODEL'):
        if issubclass(settings.PAGEMANAGER_PAGE_MODEL, Page):
            return settings.PAGEMANAGER_PAGE_MODEL
        else:
            raise ImproperlyConfigured(
                'PAGEMANAGER_PAGE_MODEL must be a subclass of '
                'pagemanager.models.Page'
            )
    return Page


def get_pagemanager_modeladmin():
    """
    Returns the model to be used by pagemanager. It must be either
    pagemanager.models.Page or a subclass thereof.
    """
    if hasattr(settings, 'PAGEMANAGER_PAGE_MODELADMIN'):
        if isinstance(settings.PAGEMANAGER_PAGE_MODELADMIN, str):
            from django.utils.importlib import import_module
            imp_path = settings.PAGEMANAGER_PAGE_MODELADMIN.split(".")
            cls_name = imp_path.pop()
            imp_path = ".".join(imp_path)
            try:
                import_module(imp_path)
            except ImportError:
                pass
            else:
                if hasattr(imp_path, cls_name):
                    return getattr(imp_path, cls_name)
        else:
            if issubclass(settings.PAGEMANAGER_PAGE_MODELADMIN, PageAdmin):
                return settings.PAGEMANAGER_PAGE_MODELADMIN
            else:
                raise ImproperlyConfigured(
                    'PAGEMANAGER_PAGE_MODELADMIN must be a subclass of '
                    'pagemanager.admin.PageAdmin'
                )
    return PageAdmin


def get_page_from_path(path):
    """
    Returns the final page in a URL-type path, validating that it lives at the
    specified placein the hierarchy as it goes. Example:
    
    >>> get_page_from_path("/i/am/a/path/")
    <Page: path>
    
    If the path is incorrect, an ``Http404`` exception is raised.
    
    """
    
    def _validate_path_with_page(page_model, parent_obj, child_slug):
        try:
            if not parent_obj:
                return page_model.objects.root_nodes().get(slug=child_slug)
            else:
                return parent_obj.get_children().get(slug=child_slug)
        except page_model.DoesNotExist:
            raise Http404("Page not found.")
    
    path_pieces = filter(bool, path.split("/"))
    validate_path = partial(_validate_path_with_page, get_pagemanager_model())
    return reduce(validate_path, path_pieces, '')