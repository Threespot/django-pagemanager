from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext as _

from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from pagemanager.permissions import get_published_status_name, \
    get_public_visibility_name
from pagemanager.managers import PageManager


def attach_generics(queryset):
    """
    Manually attach generic relations to avoid a ridiculous
    amount of database calls.
    """
    generics = {}
    for item in queryset:
        # create a dictionary of object ids per content type id
        generics.setdefault(item.layout_type_id, set()).add(item.object_id)
    # fetch all associated content types with the queryset
    content_types = ContentType.objects.in_bulk(generics.keys())
    relations = {}
    for ct, fk_list in generics.items():
        # for every content type, fetch all the object ids of that type
        ct_model = content_types[ct].model_class()
        relations[ct] = ct_model.objects.in_bulk(list(fk_list))
    for item in queryset:
        setattr(
            item, 'page_layout', relations[item.layout_type_id][item.object_id]
        )


class Page(MPTTModel):
    """
    The model of a page.

    Subclasses of this model can be used in its stead, defined in the
    PAGEMANAGER_PAGE_MODEL setting.
    """
    parent = TreeForeignKey('self', null=True, blank=True,
        related_name='children')
    order = models.IntegerField(null=True, blank=True, default=99999)
    title = models.CharField(max_length=256)
    description = models.TextField(null=True, blank=True)
    slug = models.SlugField(max_length=32)
    status = models.CharField(max_length=32, default='draft', choices=(
        ('draft', 'Draft'),
        ('review', 'Pending Review'),
        ('published', 'Published'),
    ))
    visibility = models.CharField(max_length=32, default='public', choices=(
        ('public', 'Public'),
        ('private', 'Private'),
    ))
    copy_of = models.OneToOneField('self',
        blank=True,
        null=True,
        on_delete=models.SET_NULL
    )
    is_homepage = models.BooleanField(default=False)

    # Timestamps
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    # Generic Foreign Key to subclass of PageLayout
    layout_type = models.ForeignKey(ContentType, blank=True, null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    page_layout = generic.GenericForeignKey('layout_type', 'object_id')
    materialized_path = models.TextField(blank=True)

    objects = PageManager()

    class Meta:
        get_latest_by = 'date_created'
        permissions = (
            ('view_private_pages', 'Can view private pages'),
            ('change_visibility', 'Can change page visibility'),
            ('view_draft_pages', 'Can view draft pages'),
            ('change_status', 'Can change page status'),
            ('modify_published_pages', 'Can change published pages'),
        )
        unique_together = ('parent', 'slug')
        verbose_name = 'page'
        verbose_name_plural = 'pages'

    class MPTTMeta:
        order_insertion_by = ['order']

    def __unicode__(self):
        return self.title

    def clean(self):
        """
        Only permits one page to be marked as the homepage.
        """
        if self.is_homepage:
            try:
                old_homepage = Page.objects.get(is_homepage=True)
            except Page.DoesNotExist:
                pass
            else:
                if old_homepage != self:
                    old_homepage.is_homepage = False
                    old_homepage.save()
        return super(Page, self).clean()

    def get_children(self):
        kids = super(Page, self).get_children()
        attach_generics(kids)
        return kids

    @models.permalink
    def get_absolute_url(self):
        return ('pagemanager_page', (), {'path': self.materialized_path})

    def get_add_url(self):
        return reverse('admin:%s_%s_add' % (
            self.page_layout._meta.app_label,
            self.page_layout._meta.module_name,
        )) + '?parent=%s' % self.parent.pk

    def get_edit_url(self):
        try:
            return reverse('admin:%s_%s_change' % (
                self.page_layout._meta.app_label,
                self.page_layout._meta.module_name,
            ), args=[self.page_layout.pk])
        except AttributeError:
            return ''

    def get_add_child_url(self):
        try:
            rev = reverse('admin:%s_%s_add' % (
                self._meta.app_label,
                self._meta.module_name,
            ))
            return '%s?parent=%s' % (rev, self.pk,)
        except AttributeError:
            return ''

    def get_delete_url(self):
        try:
            return reverse('admin:%s_%s_delete' % (
                self.page_layout._meta.app_label,
                self.page_layout._meta.module_name,
            ), args=[self.page_layout.pk])
        except AttributeError:
            return ''

    def get_materialized_path(self):
        """
        Return a string consiting of the current page slug, followed by
        the slug values of its ancestors, separated by a "/".
        """
        page_chain =  [a.slug for a in self.get_ancestors()]
        page_chain.append(self.slug)
        return '/'.join(page_chain)

    @property
    def path_prefix(self):
        return '/'.join([ancestor.slug for ancestor in \
            self.get_ancestors()])

    def is_visible(self):
        return self.visibility == get_public_visibility_name()
    is_visible.boolean = True

    def is_published(self):
        return self.status == get_published_status_name()
    is_published.boolean = True

    def is_unrestricted(self):
        """
        A page that is both published and visible; in other words, a page
        that will appear on the public-facing portion of the site.
        """
        return self.is_published() and self.is_visible()
    is_unrestricted.boolean = True

    @property
    def page_status(self):
        """
        A human-readable description of the page status.
        """
        status = []
        status.append(self.is_published() and "published" or "unpublished")
        status.append(self.is_visible() and "public" or "private")
        status = " and ".join(status)
        if self.copy_of:
            return "This draft copy is " + status + "."
        else:
            return "This item is " + status + "."

    def publish(self):
        """Convenience method to publish a page"""
        published_status_name = get_published_status_name()
        if self.status != published_status_name:
            self.status = published_status_name
            self.save()
            return True

    def is_draft_copy(self):
        """ Is this item a draft copy?"""
        return bool(self.copy_of)
    is_draft_copy.boolean = True

    def get_draft_copy(self):
        """
        Retrieve the draft copy of this item if it exists.
        """
        copies = self._default_manager.filter(copy_of__id=self.id)
        if copies:
            return copies[0]
        return None

    @classmethod
    def hide_from_applist(self):
        return True

    def node_id(self):
        return 'node-%s' % self.pk


class PageLayoutMeta(object):
    """
    A special Meta class for PageLayout subclasses; all properties defined
    herein are ultimately added to PageLayout._pagemanager_meta
    """
    name = None
    thumbnail = None
    template_file = None
    context = None
    fieldsets = None
    inlines = None
    exclude = None
    formfield_overrides = None
    readonly_fields = None
    admin_mixin_dict = None
    admin_media_js = None
    admin_media_css = None

    def __init__(self, opts, **kwargs):
        if opts:
            opts = opts.__dict__.items()
        else:
            opts = []
        opts.extend(kwargs.items())

        for key, value in opts:
            setattr(self, key, value)

    def __iter__(self):
        return iter([(k, v) for (k, v) in self.__dict__.items()])


class PageLayoutBase(models.base.ModelBase):
    """
    Metaclass for PageLayout models.
    """
    def __new__(cls, name, bases, attrs):
        """
        Translates the PageManagerMeta class to an instance of PageLayoutMeta,
        accessible as self._pagemanager_meta in any PageLayout subclasses.
        """
        opts = PageLayoutMeta(attrs.pop('PageManagerMeta', None))
        attrs['_pagemanager_meta'] = opts

        # Make public pointer for templating
        def get_pagemanager_meta(self):
            return self._pagemanager_meta
        attrs['pagemanager_meta'] = get_pagemanager_meta

        return super(PageLayoutBase, cls).__new__(cls, name, bases, attrs)


class PageLayout(models.Model):
    """
    An abstract model of a page layout. This class provides a base level of
    functionality for all actual page layouts.

    All subclasses should live in models.py modules of apps in
    settings.INSTALLED_APPS. This is searched at runtime.
    """

    __metaclass__ = PageLayoutBase

    page = generic.GenericRelation(Page, content_type_field='layout_type')

    class Meta:
        abstract = True

    @classmethod
    def hide_from_applist(cls):
        return True

    @classmethod
    def validate_layout(cls, parent_cls):
        """
        This overridable method provides a hook for subclasses to perform
        validation of layouts on creation.
        """
        pass

    @classmethod
    def max_num(cls, max_num):
        """
        A validation shortcut to restrict the number of pages of a specific
        PageLayout class that can exist.
        """
        existing = len(cls.objects.all())
        if existing >= max_num:
            if max_num == 1:
                plural = ''
            else:
                plural = 's'
            raise ValidationError(_(
                'Only %s page%s using the %s layout can exist.'
            ) % (max_num, plural, cls._pagemanager_meta.name,))

    @classmethod
    def require_parent(cls, parent_cls, required_parent_cls):
        """
        A validation shortcut to force a new page to be the child of a page
        with a specific PageLayout class.
        """
        if parent_cls != required_parent_cls:
            if required_parent_cls:
                raise ValidationError(_(
                    'A %s must be the child of a %s.'
                ) % (
                    cls._pagemanager_meta.name,
                    required_parent_cls._pagemanager_meta.name,
                ))
            else:
                raise ValidationError(_('A %s must not have a parent.') % \
                    cls._pagemanager_meta.name)

    def get_thumbnail(self, instance=None):
        """
        If it's necessary to define the PageLayout's thumbnail dynamically, it
        can be done here. Values here override values defined in the
        PageLayout.thumbnail property.
        """
        return getattr(self._pagemanager_meta, 'thumbnail', None)

    def get_template_name(self, instance=None):
        """
        If it's necessary to define the PageLayout's template file dynamically,
        it can be done here. Values here override values defined in the
        PageLayout.template_file property.
        """
        return getattr(self._pagemanager_meta, 'template_name', None)

    def get_context_data(self, instance=None):
        """
        If it's necessary to define the PageLayout's context dynamically, it
        can be done here. Values here override values defined in the
        PageLayout.context property.
        """
        if self._pagemanager_meta.context:
            return self._pagemanager_meta.context
        return None

    def get_redirect_url(self):
        """
        If returned value is not None, PageManagerViewMixin will return an
        HttpResponseRedirect to the URL of the returned value.
        """
        return None

    @property
    def html_id(self):
        """
        Returns a value that can be used for the layout's HTML ID.
        """
        return slugify(self._pagemanager_meta.name)


class PlaceholderPage(PageLayout):
    """
    Completely null page layout; typically used for pages that need to live in
    the navigation structure, but will be superceded by other patterns in the
    urlconf.
    """
    class Meta:
        verbose_name = 'Placeholder'
        verbose_name_plural = 'Placeholders'

    class PageManagerMeta:
        name = 'Placeholder'
        thumbnail = 'images/layouts/placeholder.png'


class RedirectPage(PageLayout):
    """
    A page that lives in the tree, but redirects to another URL when accessed.
    """
    url = models.URLField(verify_exists=False)

    class Meta:
        verbose_name = 'Redirect'
        verbose_name_plural = 'Redirects'

    class PageManagerMeta:
        name = 'Redirect'
        thumbnail = 'images/layouts/redirect.png'

    def get_redirect_url(self):
        return self.url
