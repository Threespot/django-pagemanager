from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

from pagemanager import PageAdmin
from pagemanager.models import Page

def get_staticpage_model():
    """
    Returns the model to be used by staticpages. It must be either
    staticpages.models.Page or a subclass thereof.
    """
    if hasattr(settings, 'STATICPAGES_PAGE_MODEL'):
        if issubclass(settings.STATICPAGES_PAGE_MODEL, Page):
            return settings.STATICPAGES_PAGE_MODEL
        else:
            raise ImproperlyConfigured(
                'STATICPAGES_PAGE_MODEL must be a subclass of '
                'staticpages.models.Page'
            )
    return Page


def get_staticpage_modeladmin():
    """
    Returns the model to be used by staticpages. It must be either
    staticpages.models.Page or a subclass thereof.
    """
    if hasattr(settings, 'STATICPAGES_PAGE_MODELADMIN'):
        if issubclass(settings.STATICPAGES_PAGE_MODELADMIN, PageAdmin):
            return settings.STATICPAGES_PAGE_MODELADMIN
        else:
            raise ImproperlyConfigured(
                'STATICPAGES_PAGE_MODELADMIN must be a subclass of '
                'staticpages.admin.PageAdmin'
            )
    return PageAdmin