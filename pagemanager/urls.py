from django.conf.urls.defaults import *

urlpatterns = patterns('staticpages.views',
    url(r'^pages/drag/$', 'drag_post', name="drag_post"),
)