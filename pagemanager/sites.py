from django.contrib.contenttypes.generic import GenericStackedInline
from django.core.exceptions import ImproperlyConfigured

from pagemanager.exceptions import AlreadyRegistered, NotRegistered


class PageManagerSite(object):

    def __init__(self):
        self._registry = []

    def __iter__(self):
        return self._registry.__iter__()

    def register(self, page_layout):
        """
        Registers a given page layout. If it has already been registered, this
        will raise AlreadyRegistered. If it is an abstract class, this will
        raise ImproperlyConfigured.
        """
        if hasattr(page_layout, '__iter__'):
            for item in page_layout:
                self.register(item)
        else:
            if hasattr(page_layout, '_meta.abstract') and not \
                page_layout._meta.abstract:
                raise ImproperlyConfigured((
                    'The page layout %s is abstract, so it '
                    'cannot be registered'
                ) % page_layout.__name__)
            if page_layout in self._registry:
                return False
            self._registry.append(page_layout)
            return True

    def unregister(self, page_layout):
        """
        Unregisters a given page layout. If it has not been registered, this
        will raise NotRegistered.
        """
        if page_layout not in self._registry:
            raise NotRegistered('The page layout %s cannot be unregistered as '
                'it has not been registered' % page_layout.__name__)
        self._registry.remove(page_layout)

    def get_by_name(self, name):
        """
        Returns a PageLayout class from the registry based on a passed name.
        """
        for layout in self._registry:
            if layout._pagemanager_meta.name == name:
                return layout
        return None


pagemanager_site = PageManagerSite()
