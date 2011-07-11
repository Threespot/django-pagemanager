from copy import deepcopy

from django import template
from django.contrib import admin
from django.contrib.admin.options import csrf_protect_m
from django.contrib.admin.util import unquote
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render_to_response
from django.utils.encoding import force_unicode
from django.utils.translation import ugettext as _

from reversion.admin import VersionAdmin
from threespot.orm import introspect as intr

from pagemanager.forms import PageAdminFormMixin
from pagemanager.models import Page
from pagemanager.permissions import get_permissions, get_lookup_function, \
    get_published_status_name, get_public_visibility_name, \
    get_unpublished_status_name
from pagemanager.sites import pagemanager_site

def autodiscover():
    """
    Auto-discover registered subclasses of PageLayout living in models.py files
    in any application in settings.INSTALLED_APPS by attempting to import and
    failing silently if need be.
    """
    import copy
    from django.conf import settings
    from django.utils.importlib import import_module
    from django.utils.module_loading import module_has_submodule

    for app in settings.INSTALLED_APPS:
        mod = import_module(app)
        try:
            before_import_registry = copy.copy(pagemanager_site._registry)
            import_module('%s.models' % app)
        except:
            pagemanager_site._registry = before_import_registry
            if module_has_submodule(mod, 'models'):
                raise


class PageAdmin(admin.ModelAdmin):

    fieldsets = (
        ('Basics', {
            'fields': ('title', 'slug',)
        }),
        ('Publish', {
            'fields': ('status', 'visibility',)
        }),
        ('Attributes', {
            'fields': ('parent',)
        }),
    )
    change_form_template = 'pagemanager/admin/change_form.html'
    copy_form_template = 'pagemanager/admin/copy_confirmation.html'
    prepopulated_fields = {'slug': ('title',)}
    
    def _copy_item(self, item):
        """ Create a draft copy of a published item to edit."""
        if not item.is_published:
            return None
        new_item = deepcopy(item)
        new_item.id = None
        new_item.status = get_unpublished_status_name()
        new_item.copy_of = item
        new_item.title += _(" (draft copy)")
        new_item.slug += "-draft-copy"
        # Position the new item as the next neighbor of the original
        new_item.insert_at(item, position='right')
        new_item.save()
        for obj in intr.get_referencing_objects(new_item):
            if not obj.__class__ is new_item.__class__:
                obj.pk = None
                obj.save()
                for data in intr.get_referencing_models(new_item.__class__):
                    if data['model'] is obj.__class__:
                        for m2m_field_name in data['m2m_field_names']:
                            getattr(obj, m2m_field_name).add(new_item)
        return new_item
    
    def get_urls(self):
        from django.conf.urls.defaults import patterns, url
        parents_orders_vw = self.admin_site.admin_view(self.parents_orders)
        draft_copy_vw = self.admin_site.admin_view(self.copy_view)
        draft_merge_vw = self.admin_site.admin_view(self.parents_orders)
        info = self.model._meta.app_label, self.model._meta.module_name
        more = patterns('',
            url(r'^parentsorders/$', parents_orders_vw),
            url(r'^(.+)/copy/$', draft_copy_vw, name="draft_copy"),
            url(r'^(.+)/merge/$', draft_merge_vw, name="draft_merge"),
        )
        urls = super(PageAdmin, self).get_urls()
        return more + urls

    def parents_orders(self, request):
        if request.method == 'POST':
            for page_id, values in request.POST.iteritems():
                parent, order = values.split(',')
                page = Page.objects.get(pk=int(page_id))
                try:
                    page.parent = Page.objects.get(pk=parent)
                except ValueError:
                    page.parent = None
                page.order = order
                page.save()
            return HttpResponse()
        raise Http404
    
    @csrf_protect_m
    @transaction.commit_on_success
    def copy_view(self, request, object_id, extra_context=None):
        """
        Create a draft copy of the item after user has confirmed. 
        """
        opts = self.model._meta
        app_label = opts.app_label

        obj = self.get_object(request, unquote(object_id))    

        # For our purposes, permission to copy is equivalent to 
        # permission to add.
        if not self.has_add_permission(request):
            raise PermissionDenied

        if obj is None:
            raise Http404(_(
                '%(name)s object with primary key %(key)r does not exist.') %   
                {
                    'name': force_unicode(opts.verbose_name), 
                    'key': object_id
                }
            )

        if request.POST: # The user has already confirmed the copy.
            if obj.is_draft_copy():
                self.message_user(
                    request, 
                    _('You cannot copy a draft copy.')
                )            
                return HttpResponseRedirect(request.path)
            
            if obj.get_draft_copy():
                self.message_user(
                    request, 
                    _('A draft copy already exists.')
                )
                return HttpResponseRedirect(request.path)
            
            obj_display = force_unicode(obj) + " copied."
            self.log_change(request, obj, obj_display)
            copy = self._copy_item(obj)

            self.message_user(
                request, 
                _('The %(name)s "%(obj)s" was copied successfully.') % {
                    'name': force_unicode(opts.verbose_name), 
                    'obj': force_unicode(obj_display)
                }
            )

            url = reverse(
                "admin:%s_%s_change" % (
                    app_label, 
                    self.model._meta.module_name
                ),
                args=(copy.id,)
            )
            return HttpResponseRedirect(url)

        if self.model.objects.filter(copy_of=obj).exists():
            draft_already_exists = True
            title = _("Draft Copy Exists")
            edit_copy_url = reverse(
                "admin:%s_%s_change" % (
                    app_label, 
                    self.model._meta.module_name
                ),
                args=(self.model.objects.filter(copy_of=obj)[0].id,)
            )

        else:
            draft_already_exists = False
            title = _("Are you sure?")
            edit_copy_url = None
        context = {
            "title": title,
            "object_name": force_unicode(opts.verbose_name),
            "object": obj,
            "opts": opts,
            "root_path": self.admin_site.root_path,
            "app_label": app_label,
            'draft_already_exists': draft_already_exists,
            'edit_copy_url': edit_copy_url
        }
        context.update(extra_context or {})
        context_instance = template.RequestContext(
            request, 
            current_app=self.admin_site.name
        )
        return render_to_response(self.copy_form_template, context, 
            context_instance=context_instance
        )

    def get_form(self, request, obj=None, **kwargs):
        """
        Use a bit of metaclass fun to generate a new form class that uses
        the ``forms.PageAdminFormMixin``. This is what is then passed to 
        the ``modelform_factory`` to get our form.
        """
        composed_form_class = type(
            self.form.__name__, 
            (PageAdminFormMixin, self.form,),
            dict(self.form.__dict__)
        )
        kwargs["form"] = composed_form_class
        return super(PageAdmin, self).get_form(request, obj=obj, **kwargs)
        
    def render_change_form(self, request, context, add=False, change=False, \
        form_url='', obj=None):
        """
        Function to render the change_form, used in both the add_view and
        change_view.

        Modified to include a list of all PageLayout subclasses in the context
        of Page's add_view.
        """
        if add:
            context.update({'page_layouts': pagemanager_site})
        return super(PageAdmin, self).render_change_form(request, context, \
            add, change, form_url, obj)

    def add_view(self, request, form_url='', extra_context=None):
        """
        Ensure the user is not trying to add a published or visible page if they 
        lack the necessary permissions. 
        """
        if request.method == 'POST':
            lookup_perm = get_lookup_function(request.user, get_permissions())
            # In evaluating permissions for status and visibility, it's not 
            # necessary to do more than raise a 403 if the user does not have
            # the necessary permissions; status and visibility are disabled
            # client side, so if they're not what they should be, the user is
            # doing something suspicious.
            if not lookup_perm('change_status'):
                form = self.get_form(request)(request.POST, request.FILES)
                if form.is_valid():
                    is_published_value = get_published_status_name()
                    if form.cleaned_data.get('status') == is_published_value:
                        raise PermissionDenied, "Can't create published pages."
            if not lookup_perm('change_visibility'):
                form = self.get_form(request)(request.POST, request.FILES)
                if form.is_valid():
                    is_public_value = get_public_visibility_name()
                    if form.cleaned_data.get('visibility') == is_public_value:
                        raise PermissionDenied, "Can't create public pages."
        return super(PageAdmin, self).add_view(request, 
            form_url=form_url,
            extra_context=extra_context
        )
    
    def changelist_view(self, request, extra_context=None):
        """
        Redirect the fake Page changelist_view to the real Page changelist_view.
        """
        return HttpResponseRedirect(reverse('admin:index'))

    def change_view(self, request, object_id, extra_context=None):
        """
        The 'change' admin view for this model.

        Modified to redirect to the respective PageLayout object's change_view,
        instead of the Page's. This is necessary as it's impossible to create a
        GenericInlineModelAdmin with a variable model. However, the Page model
        will always be the same, so a relation in the opposite direction is
        safe.
        """
        obj = self.get_object(request, unquote(object_id))
        layout = obj.page_layout
        layout_class_meta = layout.__class__._meta
        return HttpResponseRedirect(reverse('admin:%s_%s_change' % (
            layout_class_meta.app_label,
            layout_class_meta.module_name,
        ), args=[layout.pk]))

    def save_model(self, request, obj, form, change):
        """
        Given a model instance, saves it to the database.

        Modified to create associations between the Page object and the chosen
        PageLayout object on the initial save.
        """

        if not obj.pk:

            # Create new instance of PostLayout subclass
            layout_model = pagemanager_site.get_by_name(request.POST['layout'])
            layout = layout_model()
            layout.save()

            # Associate PostLayout subclass instance with Page
            obj.layout_type = ContentType.objects.get_for_model(layout_model)
            obj.object_id = layout.pk

        obj.save()