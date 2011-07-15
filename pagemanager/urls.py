from django.conf.urls.defaults import *

from pagemanager.views import HomepageView, PageView


urlpatterns = patterns('pagemanager.views',
    url(r'^pages/drag/$', 'drag_post', name="drag_post"),
)


def pagemanager_urlpatterns():
    return patterns('',
        url(r'^$', HomepageView.as_view(), name='pagemanager_homepage'),
        url(r'^(?P<path>.+)/$', PageView.as_view(), name='pagemanager_page'),
    )