from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission, User
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

    def _test_get_components(self):
        # FIXME: What was this supposed to do?
        self.assertTrue(self.page_layout_instance.get_components() == None)
        self.assertTrue(self.test_layout_instance.get_components() == \
            ['blog', 'news'])
        self.assertTrue(self.test_layout_instance_get.get_components() == \
            ['listing'])


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

    def _test_prevent_reregistration(self):
        # FIXME: This has been removed. Check that that's OK.
        self.site.register(self.test_layout)
        self.assertRaises(
            pagemanager.sites.AlreadyRegistered,
            self.site.register,
            self.test_layout
        )

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
