from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView

from pagemanager import app_settings


class TemplateFileMixin(object):
    def template_file(self):
        return self.get_object().page_layout._pagemanager_meta.template_file


class PageContextDataMixin(object):
    def get_context_data(self, **kwargs):
        context = super(PageContextDataMixin, self).get_context_data(**kwargs)
        context['fields'] = context['object'].page_layout
        return context


class PageView(PageContextDataMixin, DetailView, TemplateFileMixin):
    """
    View that displays a given page in the site.
    """
    context_object_name = 'page'
    model = app_settings.PAGEMANAGER_PAGE_MODEL

    def get_template_names(self):
        if self.template_name:
            return self.template_name
        return [app_settings.PAGEMANAGER_DEFAULT_TEMPLATE]

    @staticmethod
    def zero_is_none(n):
        if n:
            return n
        return None

    def get_object(self, queryset=None):
        count = 1
        queryset = self.model.objects.all()
        split = self.kwargs['path'].split('/')
        while count <= len(split):
            newslug = split[count * -1:self.zero_is_none(count * -1 + 1)]
            queryset = queryset.filter(slug=newslug[0])
            if not len(queryset):
                raise Http404
            elif len(queryset) == 1:
                return queryset[0]

    def dispatch(self, request, *args, **kwargs):
        response = super(PageView, self).dispatch(request, *args, **kwargs)
        if self.get_object().is_homepage:
            return redirect(reverse('pagemanager_homepage'))
        return response


class HomepageView(PageContextDataMixin, DetailView, TemplateFileMixin):
    """
    View that displays the single page denoted as being the homepage.
    """
    context_object_name = 'page'
    model = app_settings.PAGEMANAGER_PAGE_MODEL

    def get_template_names(self):
        if self.template_name:
            return self.template_name
        return [app_settings.PAGEMANAGER_DEFAULT_TEMPLATE]

    def get_object(self):
        try:
            return self.model.objects.get(is_homepage=True)
        except:
            raise Http404