from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.encoding import smart_str

from pagemanager.models import Page


class Command(BaseCommand):
    args = ''
    help = 'Recalculates materialized path values for all pages.'

    def handle(self, *args, **options):
        
        @transaction.commit_on_success
        def repair_pages(self):
            # Begin by rebuilding the tree.
            self.stdout.write('Rebuilding the page tree...\n')
            Page._tree_manager.rebuild()
            # Then recalculate all materialized paths.
            self.stdout.write('Recalculating materialized paths...\n')
            results = map(self.repair_page, Page.objects.all())
            num_fixed = len(filter(bool, results))
            if num_fixed:
                return "\n%d pages were fixed.\n" % num_fixed
            else:
                return "\nEverything looks OK!\n"
        
        try:
            result_message = repair_pages(self)
        except Exception, e:
            self.stdout.write("An error occured, database rolled back to existsing state.\n")
            self.stdout.write(unicode(e) + "\n")
        else:
            self.stdout.write(result_message)
        

    def repair_page(self, page):
        """
        Checks that a page's MP is what it should be, and recalculates the MP if
        needed. Returns ``True`` if page was fixed, ``False`` if it was OK.
        """
        expected_path = page.get_materialized_path()
        if expected_path != page.materialized_path:
            page_name = smart_str(unicode(page))
            self.stdout.write((
                'The page "%s" is wrong...\n\tCurrent path is "%s"'
                '\n\tPath should be "%s"\n'
            ) % (page_name, smart_str(page.materialized_path), smart_str(expected_path)))
            page.materialized_path = expected_path
            page.save()
            return True
        return False