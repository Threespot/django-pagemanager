from django.contrib import admin
from django.contrib.admin.util import unquote
from django.contrib.contenttypes import generic
from django.core.urlresolvers import reverse
from django.db import models
from django.http import HttpResponseRedirect
from django.utils.encoding import force_unicode

from reversion.admin import VersionAdmin

from pagemanager import PageAdmin
from pagemanager.app_settings import STATICPAGES_PAGE_MODEL, STATICPAGES_PAGE_MODELADMIN
from pagemanager.models import Page
from pagemanager.sites import StaticPageSite, static_page_site


# PageAdmin located in pagemanager.init to prevent a circular import
admin.site.register(STATICPAGES_PAGE_MODEL, STATICPAGES_PAGE_MODELADMIN)


class PageInline(generic.GenericStackedInline):
    """
    An inline for the Page model that's used in the PageLayout change_view.
    """
    can_delete = False
    ct_field = 'layout_type'
    ct_fk_field = 'object_id'
    extra = 1
    fieldsets = PageAdmin.fieldsets
    max_num = 1
    model = STATICPAGES_PAGE_MODEL
    template = 'pagemanager/admin/inlines/page_inline.html'
    page_inline = True


# Dynamically register admins for each registered PageLayout subclass
for page_layout in static_page_site._registry:

    class PageLayoutAdmin(VersionAdmin):
        """
        Common admin for PageLayout subclasses.
        """
        change_form_template = 'pagemanager/admin/pagelayout_change_view.html'
        formfield_overrides = {}
        inlines = [PageInline]
        model = page_layout
        exclude = []
        verbose_name = None
        verbose_name_meta = None

        def changelist_view(self, request, extra_context=None):
            """
            Redirect the PageLayout changelist_view to the Page changelist_view
            """
            return HttpResponseRedirect(reverse('admin:index'))

        def add_view(self, request, form_url='', extra_context=None):
            """
            Redirect the PageLayout add_view to the Page add_view
            """
            return HttpResponseRedirect(reverse('admin:pagemanager_page_add'))

        def response_change(self, request, obj):
            """
            There are three buttons that you can press when editing a
            PageLayout object:

            - If you press "Save", this redirects you to the admin index page
              (i.e. the Page listing page)
            - If you press "Save and continue editing", this redirects you to
              the current page.
            - If you press "Save and add another", this redirects you to the
              Page add_view.
            """
            opts = obj._meta
            verbose_name = opts.verbose_name
            if obj._deferred:
                opts_ = opts.proxy_for_model._meta
                verbose_name = opts_.verbose_name
            pk_value = obj._get_pk_val()

            msg = 'The page "%(obj)s" was changed successfully.' % {
                'name': force_unicode(verbose_name),
                'obj': force_unicode(obj.page.all()[0])
            }
            if "_continue" in request.POST:
                self.message_user(request, msg + ' ' + \
                    "You may edit it again below.")
                return HttpResponseRedirect(request.path)
            elif "_addanother" in request.POST:
                self.message_user(request, msg + ' ' + \
                    "You may add another page below.")
                return HttpResponseRedirect(reverse('admin:pagemanager_page_add'))
            else:
                return HttpResponseRedirect(reverse('admin:index'))


    # Overrides provided in the PageLayout subclass' StaticPageMeta class
    meta = page_layout._meta
    sp_meta = page_layout._staticpages_meta

    if sp_meta.formfield_overrides:
        PageLayoutAdmin.formfield_overrides.update(sp_meta.formfield_overrides)
    if sp_meta.fieldsets:
        PageLayoutAdmin.fieldsets = sp_meta.fieldsets
    if meta.verbose_name:
        PageLayoutAdmin.verbose_name = meta.verbose_name
    if meta.verbose_name_plural:
        PageLayoutAdmin.verbose_name_plural = meta.verbose_name_plural
    if sp_meta.inlines:
        PageLayoutAdmin.inlines = PageLayoutAdmin.inlines + sp_meta.inlines
    if sp_meta.exclude:
        PageLayoutAdmin.exclude = PageLayoutAdmin.exclude + sp_meta.exclude

    admin.site.register(page_layout, PageLayoutAdmin)