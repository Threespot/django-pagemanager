from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView

from pagemanager import app_settings


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
        count = 1
        queryset = self.model.objects.all()
        split = self.kwargs['path'].split('/')
        while count <= len(split):
            newslug = split[count * -1:self.zero_is_none(count * -1 + 1)]
            queryset = queryset.filter(slug=newslug[0])
            if not len(queryset):
                raise Http404
            elif len(queryset) == 1:
                self.content_object = queryset[0]
                return self.content_object

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