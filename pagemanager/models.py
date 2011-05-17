from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.db import models
from django.template.defaultfilters import slugify

from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel, MPTTModelBase


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

    # Timestamps
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    # Generic Foreign Key to subclass of PageLayout
    layout_type = models.ForeignKey(ContentType, blank=True, null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    page_layout = generic.GenericForeignKey('layout_type', 'object_id')

    class Meta:
        get_latest_by = 'date_created'
        permissions = (
            ('can_view_draft_pages', 'Can view draft pages'),
            ('can_publish_pages', 'Can publish pages'),
            ('can_view_private_pages', 'Can view private pages'),
        )
        unique_together = ('parent', 'slug')
        verbose_name = 'page'
        verbose_name_plural = 'pages'

    class MPTTMeta:
        order_insertion_by = ['order']

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return '/' + self.path_prefix

    def get_add_url(self):
        return reverse('admin:%s_%s_add' % (
            self.page_layout._meta.app_label,
            self.page_layout._meta.module_name,
        )) + '?parent=%s' % self.parent.pk

    def get_edit_url(self):
        return reverse('admin:%s_%s_change' % (
            self.page_layout._meta.app_label,
            self.page_layout._meta.module_name,
        ), args=[self.page_layout.pk])

    def get_add_child_url(self):
        rev = reverse('admin:%s_%s_add' % (
            self._meta.app_label,
            self._meta.module_name,
        ))
        return '%s?parent=%s' % (rev, self.pk,)

    def get_delete_url(self):
        return reverse('admin:%s_%s_delete' % (
            self.page_layout._meta.app_label,
            self.page_layout._meta.module_name,
        ), args=[self.page_layout.pk])

    @property
    def path_prefix(self):
        return '/'.join([ancestor.slug for ancestor in self.get_ancestors()])

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
        Translates the StaticPageMeta class to an instance of PageLayoutMeta,
        accessible as self._layout_meta in any PageLayout subclasses.
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

    def get_thumbnail(self, instance=None):
        """
        If it's necessary to define the PageLayout's thumbnail dynamically, it
        can be done here. Values here override values defined in the
        PageLayout.thumbnail property.
        """
        if self._pagemanager_meta.thumbnail:
            return self._pagemanager_meta.thumbnail
        return None

    def get_template_file(self, instance=None):
        """
        If it's necessary to define the PageLayout's template file dynamically,
        it can be done here. Values here override values defined in the
        PageLayout.template_file property.
        """
        if self._pagemanager_meta.template_file:
            return self._pagemanager_meta.template_file
        return None

    def get_context_data(self, instance=None):
        """
        If it's necessary to define the PageLayout's context dynamically, it can
        be done here. Values here override values defined in the
        PageLayout.context property.
        """
        if self._pagemanager_meta.context:
            return self._pagemanager_meta.context
        return None

    @property
    def html_id(self):
        """
        Returns a value that can be used for the layout's HTML ID.
        """
        return slugify(self._pagemanager_meta.name)