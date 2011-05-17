from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

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
        if issubclass(settings.PAGEMANAGER_PAGE_MODELADMIN, PageAdmin):
            return settings.PAGEMANAGER_PAGE_MODELADMIN
        else:
            raise ImproperlyConfigured(
                'PAGEMANAGER_PAGE_MODELADMIN must be a subclass of '
                'pagemanager.admin.PageAdmin'
            )
    return PageAdmin