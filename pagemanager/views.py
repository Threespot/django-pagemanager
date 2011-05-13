from django.views.generic import DetailView
from django.http import Http404

import app_settings

model = app_settings.STATICPAGES_PAGE_MODEL

class StaticPageView(DetailView):
    context_object_name = 'page'
    model = app_settings.STATICPAGES_PAGE_MODEL

    # def get_context_data(self, **kwargs):
    #     context = super(StaticPageView, self).get_context_data(**kwargs)
    #     import pdb; pdb.set_trace()
    #     context.update(context['object'].page_layout.__class__.context)
    #     return context

    def get_template_names(self):
        if self.template_name:
            return self.template_name
        return [app_settings.STATICPAGES_DEFAULT_TEMPLATE]

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
            newslug = split[count*-1:self.zero_is_none(count*-1+1)]
            queryset = queryset.filter(slug=newslug[0])
            if not len(queryset):
                raise Http404
            elif len(queryset) == 1:
                return queryset[0]