from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView

from pagemanager import app_settings
from pagemanager.models import RedirectPage
from pagemanager.util import get_page_from_path


class PageManagerViewMixin(object):
    """
    Mixin that provides base functionality for all views used with pagemanager
    """
    context_object_name = 'page'
    content_object = None
    model = app_settings.PAGEMANAGER_PAGE_MODEL

    def get_template_names(self):
        return [self.get_object().page_layout.pagemanager_meta().template_file]

    def template_file(self):
        return self.get_object().page_layout.pagemanager_meta().template_file

    def get_context_data(self, **kwargs):
        context = super(PageManagerViewMixin, self).get_context_data(**kwargs)
        context['fields'] = context['object'].page_layout
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super(PageManagerViewMixin, self).dispatch(request, *args, \
            **kwargs)

        redirect_url = self.object.page_layout.get_redirect_url()
        if redirect_url:
            return HttpResponseRedirect(redirect_url)

        return response


class PageView(PageManagerViewMixin, DetailView):
    """
    View that displays a given page in the site.
    """
    context_object_name = 'page'
    model = app_settings.PAGEMANAGER_PAGE_MODEL

    @staticmethod
    def zero_is_none(n):
        if n:
            return n
        return None

    def get_object(self, queryset=None):
        if self.content_object:
            return self.content_object
        return get_page_from_path(self.kwargs['path'])

    def dispatch(self, request, *args, **kwargs):
        response = super(PageView, self).dispatch(request, *args, **kwargs)
        if self.get_object().is_homepage:
            return redirect(reverse('pagemanager_homepage'))
        return response


class HomepageView(PageManagerViewMixin, DetailView):
    """
    View that displays the single page denoted as being the homepage.
    """
    def get_object(self):
        if self.content_object:
            return self.content_object
        try:
            self.content_object = self.model.objects.get(is_homepage=True)
            return self.content_object
        except:
            raise Http404
