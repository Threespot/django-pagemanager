from django.conf import settings
from django.db.models import get_model

from pagemanager.util import get_staticpage_model, get_staticpage_modeladmin

STATICPAGES_DEFAULT_TEMPLATE = getattr(settings,
    'STATICPAGES_DEFAULT_TEMPLATE',
    'staticpages/base.html'
)
STATICPAGES_PAGE_MODEL = get_staticpage_model()
STATICPAGES_PAGE_MODELADMIN = get_staticpage_modeladmin()