from django.conf.urls.defaults import *

from pagemanager.views import PageView


urlpatterns = patterns('pagemanager.views',
    url(r'^pages/drag/$', 'drag_post', name="drag_post"),
)


def pagemanager_urlpatterns():
    return patterns('',
        (r'^(?P<path>.+)$', PageView.as_view()),
    )
