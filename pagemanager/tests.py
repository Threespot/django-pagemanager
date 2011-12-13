from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.db import models
from django.test import TestCase
from django.utils import unittest

import pagemanager
from pagemanager.exceptions import AlreadyRegistered, NotRegistered
from pagemanager.models import Page, PageLayout


class TestHomepageLayout(PageLayout):
    """
    A page layout class for testing. 
    """
    body = models.TextField()

    class PageManagerMeta:
        name = 'Homepage'
        thumbnail = 'pagemanager/homepage.jpg'
        template_name = 'pagemanager/homepage.html'
        context = {'foo': 'bar'}
        components = ['blog', 'news']


class Foo(models.Model):
    bar = models.TextField()


class FooLayout(PageLayout):
    foos = models.ManyToManyField(Foo)


class TestListingPageLayout(PageLayout):
    """
    A second page layout class for testing. 
    """    
    name = 'Landing Page'
    base = 'listing'

    def get_thumbnail(self, instance=None):
        return '%s.jpg' % self.base

    def get_template_name(self, instance=None):
        return '%s.html' % self.base

    def get_context_data(self, instance=None):
        return {'foo': '%s' % self.base}

    def get_components(self, instance=None):
        return [self.base]


class PageManagerSiteTest(unittest.TestCase):
    """
    Test that a page manager site can successfully be initialized.
    """
    def setUp(self):
        self.site = pagemanager.sites.PageManagerSite()

    def test_initilization(self):
        self.assertTrue(self.site._registry == [])

    def _test_dependency_check(self):
        # FIXME: What was this supposed to do?
        self.site.check_dependencies()
        self.assertTrue(True)


class PageLayoutModelTest(unittest.TestCase):
    """
    Test the behavior of the internals of the PageLayout class (including
    the behavior of PageLayoutMeta).
    """
    def setUp(self):
        self.page_layout_instance = PageLayout()
        self.test_layout = TestHomepageLayout
        self.test_layout_instance = self.test_layout()
        self.test_layout_instance_get = TestListingPageLayout()

    def test_initialization(self):
        self.assertTrue(isinstance(
            pagemanager.pagemanager_site,
            pagemanager.sites.PageManagerSite
        ))

    def test_get_thumbnail(self):
        self.assertTrue(self.page_layout_instance.get_thumbnail() == None)
        self.assertTrue(self.test_layout_instance.get_thumbnail() == \
            'pagemanager/homepage.jpg')
        self.assertTrue(self.test_layout_instance_get.get_thumbnail() == \
            'listing.jpg')

    def test_get_template_file(self):
        self.assertTrue(self.page_layout_instance.get_template_name() == None)
        self.assertTrue(self.test_layout_instance.get_template_name() == \
            'pagemanager/homepage.html')
        self.assertTrue(self.test_layout_instance_get.get_template_name() == \
            'listing.html')

    def test_get_context_data(self):
        self.assertTrue(self.page_layout_instance.get_context_data() == None)
        self.assertTrue(self.test_layout_instance.get_context_data() == \
            {'foo': 'bar'})
        self.assertTrue(self.test_layout_instance_get.get_context_data() == \
            {'foo': 'listing'})


class RegistrationTest(unittest.TestCase):
    
    def setUp(self):
        """
        Create an initial site for the test class to use for registering things
        and a test layout as well.
        """
        self.site = pagemanager.sites.PageManagerSite()
        self.test_layout = TestHomepageLayout

    def test_registration(self):
        """ Verify the layouts are registered properly."""
        self.site.register(self.test_layout)
        self.assertTrue(self.test_layout in self.site._registry)

    def test_unregistration(self):
        """ Verify the layouts can be unregistered properly."""
        self.site.register(self.test_layout)
        self.site.unregister(self.test_layout)
        self.assertFalse(self.test_layout in self.site._registry)

    def test_prevent_wrong_subclass_registration(self):
        """ 
        Verify that only layouts that subclass ``PageLayout`` can be
        registered.
        """
        class SpuriousLayout(object):
            pass
        
        self.assertRaises(
            pagemanager.sites.ImproperlyConfigured,
            self.site.register,
            SpuriousLayout
        )        
    
    def test_prevent_abstract_registration(self):
        """
        Verify that abstract models cannot be registered.
        """
        self.assertRaises(
            pagemanager.sites.ImproperlyConfigured,
            self.site.register,
            PageLayout
        )

    def test_prevent_unregistration_of_unregistered(self):
        """
        Verify that you can only unregister a class once.
        """
        self.assertRaises(
            pagemanager.sites.NotRegistered,
            self.site.unregister,
            self.test_layout
        )


class TestPageBehaviors(TestCase):
    
    fixtures = ['pagemanager_test_data.json']
    
    def __init__(self, *args, **kwargs):
        super(TestPageBehaviors, self).__init__(*args, **kwargs)
        from pagemanager.sites import pagemanager_site
        self.site = pagemanager_site
        self.site.register(TestHomepageLayout)

    def fix_generic_rels(self):
        """
        Becuase fixture data relies on the state of the content types DB
        to make generic relations work, and becuase the content types DB
        contents are unknown at runtime, this function makes sure all
        ``Page`` objects have the correct generic relation to instances of
        the ``TestHomepageLayout`` created by the fixture.
        """
        layout_type = ContentType.objects.get(
            app_label="pagemanager",
            model="testhomepagelayout"
        )
        for page in Page.objects.all():
            page.layout_type = layout_type
            page.save()

    def test_page_status_and_visibility_behavior(self):
        """
        Tests that methods and attributes having to do with publishing
        and unpublishing of pages behave as expected. 
        """
        root_page = Page.objects.get(pk=1)
        self.assertFalse(root_page.is_published())
        self.assertFalse(root_page.is_unrestricted())
        root_page.publish()
        self.assertTrue(root_page.is_published())
        self.assertTrue(root_page.is_visible())
        self.assertTrue(root_page.is_unrestricted())

    def test_page_permissions(self):
        """
        Verify that user permissions work as expected. This test tries various
        permutations of user permissions to ensure that unauthorized admin users
        cannot gain access to or modify data.
        """
        # Create a new staff user.
        test_user_props = {
            'name': 'test_user',
            'email': 'test@example.com',
            'password': 'testpassword'
        }
        test_user = User.objects.create_user(
            test_user_props['name'],
            test_user_props['email'],
            test_user_props['password']
        )
        test_user.is_staff = True
        test_user.save()
        
        # Give user the base set of permissions for the 
        # ``TestHomepageLayout`` and ``Page`` models.
        for codename in (
            'add_testhomepagelayout',
            'change_testhomepagelayout',
            'delete_testhomepagelayout',
            'add_page',
            'change_page',
            'delete_page',
        ):
            permission = Permission.objects.get(codename=codename)
            test_user.user_permissions.add(permission)
        self.fix_generic_rels()
        root_page = Page.objects.get(pk=1)
        self.client.login(
            username=test_user_props['name'], 
            password=test_user_props['password']
        )
        change_page_url = reverse("admin:pagemanager_testhomepagelayout_change",
            args=[root_page.pk]
        )
        # User should not be able to view unpublished page.
        
        response = self.client.get(change_page_url)
        self.assertEqual(response.status_code, 403)
        root_page.publish()
        response = self.client.get(change_page_url)
        self.assertEqual(response.status_code, 200)
        # User should not be able to view private page.
        root_page.visibility = "private"
        root_page.save()
        response = self.client.get(change_page_url)
        self.assertEqual(response.status_code, 403)
        # Add view_private_pages permission and retest.
        permission = Permission.objects.get(codename='view_private_pages')
        test_user.user_permissions.add(permission)
        response = self.client.get(change_page_url)
        self.assertEqual(response.status_code, 200)
        # Add view_draft_pages permission and retest.
        root_page.status = 'draft'
        root_page.save()
        response = self.client.get(change_page_url)
        self.assertEqual(response.status_code, 403)
        permission = Permission.objects.get(codename='view_draft_pages')
        test_user.user_permissions.add(permission)
        response = self.client.get(change_page_url)
        self.assertEqual(response.status_code, 200)
        # Test making changes to data.
        data = {
            'pagemanager-page-layout_type-object_id-TOTAL_FORMS': '1',
            'pagemanager-page-layout_type-object_id-INITIAL_FORMS': '1',
            'pagemanager-page-layout_type-object_id-MAX_NUM_FORMS': '1',
            'pagemanager-page-layout_type-object_id-0-title': 'Root Page',
            'pagemanager-page-layout_type-object_id-0-slug': 'root-page',
            'pagemanager-page-layout_type-object_id-0-status': 'draft',
            'pagemanager-page-layout_type-object_id-0-visibility': 'private',
            'pagemanager-page-layout_type-object_id-0-parent': '',
            'pagemanager-page-layout_type-object_id-0-id': '1',
            ''
            'body': 'Sample body content'
        }
        response = self.client.post(change_page_url, data)
        self.assertRedirects(response, reverse("admin:index"))
        # Try to publish page.
        data['pagemanager-page-layout_type-object_id-0-status'] = 'published'
        response = self.client.post(change_page_url, data)
        self.assertRedirects(response, change_page_url)
        # Add change_status permission and retry.
        permission = Permission.objects.get(codename='change_status')
        test_user.user_permissions.add(permission)
        response = self.client.post(change_page_url, data)
        self.assertRedirects(response, reverse("admin:index"))
        # Try to change data of published page.
        data['body'] = "Yet more sample body content."
        response = self.client.post(change_page_url, data)
        self.assertEqual(response.status_code, 403)
        # Add modify_published_pages permission and retry.
        permission = Permission.objects.get(codename='modify_published_pages')
        test_user.user_permissions.add(permission)
        response = self.client.post(change_page_url, data)
        self.assertRedirects(response, reverse("admin:index"))
        # Try to change visibility:
        data['pagemanager-page-layout_type-object_id-0-visibility'] = 'public'
        response = self.client.post(change_page_url, data)
        self.assertRedirects(response, change_page_url)
        # Add change_visibility permission and retry.
        permission = Permission.objects.get(codename='change_visibility')
        test_user.user_permissions.add(permission)
        response = self.client.post(change_page_url, data)
        self.assertRedirects(response, reverse("admin:index"))

    def test_m2m_preservation_in_copying_and_merging(self):
        root_page = Page.objects.get(pk=1)
        foo_layout = FooLayout()
        foo_layout.save()
        for n in range(1, 3):
            foo = Foo(bar="%d" % n)
            foo.save()
            foo_layout.foos.add(foo)
        root_page.page_layout = foo_layout
        root_page.save()
        # Create a new staff user.
        test_user_props = {
            'name': 'test_user',
            'email': 'test@example.com',
            'password': 'testpassword'
        }
        test_user = User.objects.create_user(
            test_user_props['name'],
            test_user_props['email'],
            test_user_props['password']
        )
        test_user.is_superuser = True
        test_user.is_staff = True
        test_user.save()    
        log = self.client.login(
            username=test_user_props['name'], 
            password=test_user_props['password']
        )
        copy_url = reverse("admin:draft_copy", args=(foo_layout.pk,))
        response = self.client.get(copy_url)
        self.assertEqual(response.context['object'], root_page)
        self.assertTrue(not root_page.get_draft_copy())
        response = self.client.post(copy_url, {'post': 'yes'})
        draft_copy = root_page.get_draft_copy()
        self.assertTrue(isinstance(draft_copy, Page))
        self.assertEqual(draft_copy.page_layout.foos.count(), 2)
        self.assertEqual(draft_copy.page_layout.foos.all()[0].bar, '1')
        self.assertEqual(draft_copy.page_layout.foos.all()[1].bar, '2')
        merge_url = reverse("admin:draft_merge", args=(draft_copy.pk,))
        response = self.client.get(merge_url)
        self.assertEqual(response.context['object'], draft_copy)
        response = self.client.post(merge_url, {'post': 'yes'})
        self.assertTrue(not Page.objects.draft_copies())
