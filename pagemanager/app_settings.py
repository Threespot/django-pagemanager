from django.conf import settings
from django.db.models import get_model

from pagemanager.util import get_pagemanager_model, get_pagemanager_modeladmin

PAGEMANAGER_DEFAULT_TEMPLATE = getattr(settings,
    'PAGEMANAGER_DEFAULT_TEMPLATE',
    'staticpages/base.html'
)
PAGEMANAGER_PAGE_MODEL = get_pagemanager_model()
PAGEMANAGER_PAGE_MODELADMIN = get_pagemanager_modeladmin()