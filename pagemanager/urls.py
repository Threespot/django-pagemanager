from django.conf.urls.defaults import *

urlpatterns = patterns('pagemanager.views',
    url(r'^pages/drag/$', 'drag_post', name="drag_post"),
)