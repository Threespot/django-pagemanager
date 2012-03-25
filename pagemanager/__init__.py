from copy import deepcopy
from itertools import chain

from django import template
from django.contrib import admin
from django.contrib.admin.options import csrf_protect_m
from django.contrib.admin.util import get_deleted_objects, unquote
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import transaction, router
from django.db.models.fields import AutoField
from django.db.models.fields.related import RelatedField, ManyToManyField
from django.forms import ModelForm
from django.http import HttpResponseRedirect, HttpResponseBadRequest,\
    HttpResponse, Http404
from django.shortcuts import render_to_response
from django.utils.encoding import force_unicode
from django.utils.html import escape
from django.utils.translation import ugettext as _

from reversion.admin import VersionAdmin
from threespot.orm import introspect

from pagemanager.forms import PageAdminFormMixin
from pagemanager.models import Page
from pagemanager.permissions import get_permissions, get_lookup_function, \
    get_published_status_name, get_public_visibility_name, \
    get_unpublished_status_name
from pagemanager.sites import pagemanager_site

DRAFT_POSTFIX = _(" (draft copy)")

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


class PageAdminForm(ModelForm):

    def clean(self):
        """
        Perform additional validation of rules regarding the PageLayout's
        existence, rather than those validating the PageLayout's data (which
        can be handled in PageLayoutAdmin.full_clean).

        This is done by calling the validate_layout classmethod on the class
        of the proposed layout, passing it the class of the parent's layout.

        Unfortunately, this validation only occurs in the admin; it is not
        performed when creating Page objects otherwise.
        """
        layout_cls = pagemanager_site.get_by_name(self.data['layout'])
        try:
            parent_cls = self.cleaned_data['parent'].page_layout.__class__
        except AttributeError:
            parent_cls = None
        layout_cls.validate_layout(parent_cls)
        return self.cleaned_data


class PageAdmin(admin.ModelAdmin):
    form = PageAdminForm
    fieldsets = (
        ('Basics', {
            'fields': ('title', 'slug',)
        }),
        ('Publish', {
            'fields': ('status', 'visibility',)
        }),
        ('Attributes', {
            'fields': ('parent', 'is_homepage', 'description',)
        }),
    )
    change_form_template = 'pagemanager/admin/change_form.html'
    copy_form_template = 'pagemanager/admin/copy_confirmation.html'
    merge_form_template = "pagemanager/admin/merge_confirmation.html"
    prepopulated_fields = {'slug': ('title',)}

    def _copy_page(self, page):
        """ Create a draft copy of a published item to edit."""
        if not page.is_published:
            return None
        original_pk = page.pk
        original_layout_pk = page.page_layout.pk
        page.pk = None
        new_page = page
        original_page = Page.objects.get(pk=original_pk)
        # Position the new item as the next neighbor of the original
        new_page.insert_at(original_page, position='right')
        new_page.status = get_unpublished_status_name()
        new_page.copy_of = original_page
        new_page.title += DRAFT_POSTFIX
        new_page.slug += "-draft-copy"
        new_page.page_layout = None
        new_page.save()
        ignore = ['copy_of', 'layout_type']
        fk_rels = [f.name for f in self.model._meta.fields \
            if issubclass(f.__class__, RelatedField) and f.name not in ignore
        ]
        for field in fk_rels:
            setattr(new_page, field, getattr(original_page, field))
        m2m_rels = [f.name for f, x in self.model._meta.get_m2m_with_model()]
        for field in m2m_rels:
            setattr(new_page, field, getattr(original_page, field).all())
        # Create a copy of the layout and attach to the new item.
        new_layout = self._copy_object(original_page.page_layout)
        original_layout = new_layout.__class__.objects.get(
            pk=original_layout_pk
        )
        fk_rels = [f.name for f in original_layout._meta.fields \
            if issubclass(f.__class__, RelatedField) and f.name not in ignore
        ]
        for field in fk_rels:
            setattr(new_layout, field, getattr(original_layout, field, None))
        m2m_rels = [f.name for f, x in \
            original_layout._meta.get_m2m_with_model() if f.name != 'page'
        ]
        for field in m2m_rels:
            m2m_objects = getattr(original_layout, field).all()
            getattr(new_layout, field, ).add(*m2m_objects)
        new_layout.save()
        new_page.page_layout = new_layout
        new_page.save()
        return new_page

    @staticmethod
    def _get_copy_method_name(obj):
        """
        Attempts to determine what the method name to copy an object might be.
        The following pattern is used::

            _copy_{{object app label}}_{{ object model name}}

        If this method exists on this class, it will be used instead of the
        generic ``_copy_object`` method.
        """
        return "_copy_%(app_label)s_%(module_name)s" % {
            'app_label': obj._meta.app_label,
            'module_name': obj._meta.module_name
        }

    def _copy_object(self, obj):
        """
        Generic function to copy an object. All this does is set the pk to
        ``None``, save the object, and return it. This will be used to copy
        objects associated with a page unless an overriding method with the
        app label and model name is created.
        """
        obj.pk = None
        obj.save()
        return obj

    def _merge_item(self, original, copy):
        """ Delete original, clean up and publish copy."""
        children = set(list(original.children.all()) + list(copy.children.all()))
        # Remove the postfix from the title, if it hasn't already been changed.
        if copy.title.endswith(DRAFT_POSTFIX):
            copy.title = copy.title[:-1 * len(DRAFT_POSTFIX)]

        # Copy values from copy to original, excepting any AutoField instances
        # and the slug field.
        for field in copy._meta.fields:
            if not issubclass(AutoField, field.__class__) and field.name not \
                in ['slug', 'status']:
                field_name = field.name
                setattr(original, field_name, getattr(copy, field_name))

        copy.delete()
        original.copy_of = None
        original.save()

        # Ensure that all children in both the original and the copy are made
        # children of the original.
        for child in children:
            child.move_to(original, position='last-child')

        return copy

    def get_urls(self):
        from django.conf.urls.defaults import patterns, url
        parents_orders_vw = self.admin_site.admin_view(
            self.parents_orders_view
        )
        draft_copy_vw = self.admin_site.admin_view(self.copy_view)
        draft_merge_vw = self.admin_site.admin_view(self.merge_view)
        info = self.model._meta.app_label, self.model._meta.module_name
        more = patterns('',
            url(r'^parentsorders/$', parents_orders_vw),
            url(r'^(.+)/copy/$', draft_copy_vw, name="draft_copy"),
            url(r'^(.+)/merge/$', draft_merge_vw, name="draft_merge"),
        )
        urls = super(PageAdmin, self).get_urls()
        return more + urls

    def parents_orders_view(self, request):
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
                    'key': escape(object_id)
                }
            )

        if request.POST:  # The user has already confirmed the copy.
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
            copy = self._copy_page(obj)

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

    @csrf_protect_m
    @transaction.commit_on_success
    def merge_view(self, request, object_id, extra_context=None):
        """
        The 'merge' admin view for this model. Allows a user to merge a draft
        copy back over the original.
        """
        opts = self.model._meta
        app_label = opts.app_label

        obj = self.get_object(request, unquote(object_id))

        # For our purposes, permission to merge is equivalent to
        # has_change_permisison and has_delete_permission.
        if not self.has_change_permission(request, obj) \
            or not self.has_delete_permission(request, obj):
            raise PermissionDenied

        if obj is None:
            raise Http404(_(
                '%(name)s object with primary key %(key)r does not exist.') %
                {
                    'name': force_unicode(opts.verbose_name),
                    'key': escape(object_id)
                }
            )

        if not obj.is_draft_copy:
            return HttpResponseBadRequest(_(
                'The %s object could not be merged because it is not a'
                'draft copy. There is nothing to merge it into.'
            ) % force_unicode(opts.verbose_name))

        # Populate deleted_objects, a data structure of all related objects
        # that will also be deleted when this copy is deleted.
        all_objects = introspect.get_referencing_objects(obj.copy_of)
        all_objects.insert(0, obj.copy_of)
        using = router.db_for_write(self.model)
        (deleted_objects, perms_needed, protected) = get_deleted_objects(
            all_objects, opts, request.user, self.admin_site, using
        )
        # Flatten nested list:
        deleted_objects = map(
            lambda i: hasattr(i, '__iter__') and i or [i],
            deleted_objects
        )
        deleted_objects = chain(*deleted_objects)
        deleted_objects = list(deleted_objects)
        # ``get_deleted_objects`` is zealous and will add the draft copy to
        # the list of things to be deleted. This needs to be removed.
        obj_url = reverse("admin:pagemanager_page_change", args=(obj.pk,))
        obj_name = unicode(obj)
        deleted_objects = filter(
            lambda link: obj_url not in link,
            deleted_objects
        )
        # Filter out child pages: these will be preserved too.
        for child in obj.copy_of.children.all():
            child_url = reverse("admin:pagemanager_page_change", args=(child.pk,))
            deleted_objects = filter(
                lambda link: child_url not in link,
                deleted_objects
            )
        # Populate replacing_objects, a data structure of all related objects
        # that will be replacing the originals.
        replacing_objects = introspect.get_referencing_objects(obj)
        replacing_objects.insert(0, obj)
        (replacing_objects, perms_needed, protected) = get_deleted_objects(
            replacing_objects, opts, request.user, self.admin_site, using
        )
        # Flatten nested list:
        replacing_objects = map(
            lambda i: hasattr(i, '__iter__') and i or [i],
            replacing_objects
        )
        replacing_objects = chain(*replacing_objects)
        replacing_objects = list(replacing_objects)

        if request.POST:  # The user has already confirmed the merge.
            if perms_needed:
                raise PermissionDenied
            obj_display = force_unicode(obj) + " merged."
            self.log_change(request, obj, obj_display)

            original = obj.copy_of
            self._merge_item(original, obj)

            self.message_user(
                request,
                _('The %(name)s "%(obj)s" was merged successfully.') % {
                    'name': force_unicode(opts.verbose_name),
                    'obj': force_unicode(obj_display)
                }
            )
            redirect_url = reverse("admin:pagemanager_page_change",
                args=(original.pk,)
            )
            return HttpResponseRedirect(redirect_url)

        context = {
            "title": _("Are you sure?"),
            "object_name": force_unicode(opts.verbose_name),
            "object": obj,
            "escaped_original": force_unicode(obj.copy_of),
            "deleted_objects": deleted_objects,
            "replacing_objects": replacing_objects,
            "perms_lacking": perms_needed,
            "opts": opts,
            "root_path": self.admin_site.root_path,
            "app_label": app_label,
        }
        context.update(extra_context or {})
        context_instance = template.RequestContext(
            request,
            current_app=self.admin_site.name
        )
        return render_to_response(self.merge_form_template, context,
            context_instance=context_instance
        )

    def render_change_form(self, request, context, add=False, change=False, \
        form_url='', obj=None):
        """
        Function to render the change_form, used in both the add_view and
        change_view.

        Modified to include a list of all PageLayout subclasses in the context
        of Page's add_view.
        """
        if add:
            context.update({
                'page_layouts': sorted(pagemanager_site._registry, \
                    key=lambda x: x._pagemanager_meta.name)
            })
        return super(PageAdmin, self).render_change_form(request, context, \
            add, change, form_url, obj)

    def add_view(self, request, form_url='', extra_context=None):
        """
        Ensure the user is not trying to add a published or visible page if
        they lack the necessary permissions.
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
                        raise PermissionDenied("Can't create published pages.")
            if not lookup_perm('change_visibility'):
                form = self.get_form(request)(request.POST, request.FILES)
                if form.is_valid():
                    is_public_value = get_public_visibility_name()
                    if form.cleaned_data.get('visibility') == is_public_value:
                        raise PermissionDenied("Can't create public pages.")
        return super(PageAdmin, self).add_view(request,
            form_url=form_url,
            extra_context=extra_context
        )

    def changelist_view(self, request, extra_context=None):
        """
        Redirect the fake Page changelist_view to the real Page
        ``changelist_view``.
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
        if not obj:
            raise Http404("Page not found.")
        layout = obj.page_layout
        if not layout:
            raise Http404("No layout found for this page.")
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
