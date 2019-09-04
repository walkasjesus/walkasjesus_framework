from concurrent.futures.thread import ThreadPoolExecutor

from bible_lib import BibleFactory
from bible_lib.bible_api.services import Services
from django.core.management import BaseCommand

from commandments_app.models import BibleReferences, BibleTranslation


class Command(BaseCommand):
    def handle(self, *args, **options):
        bibles = BibleTranslation().all_in_supported_languages()

        if 'bible_id' not in options:
            print('Please provide a bible_id as first argument. ')
            print('The following ids are accepted: ')
            for bible in bibles:
                print(f'id: {bible.id} name: {bible.name}')
            return

        bible_id = options['bible_id']

        if bible_id not in [b.id for b in bibles]:
            print(f'bible_id {bible_id} was not found in the list of available bibles.')
            return

        self.load_bible_verses(bible_id)
        
        cache = Services().cache
        cache.store_state()

    def load_bible_verses(self, bible_id: str):
        bible_references = BibleReferences()
        bible_references.bible = BibleFactory().create(bible_id)

        # Just retrieve the text of all references and it will automatically be cached by the bible_lib
        refs = list(bible_references.primary()) + list(bible_references.secondary()) + list(bible_references.tertiary())

        with ThreadPoolExecutor(max_workers=16) as worker_pool:
            worker_pool.map(self.load_verse, refs)

    def load_verse(self, bible_reference):
        print(f'loading: {bible_reference}')
        # Calling the text() method will retrieve the content, it will be cached by the bible_lib itself.
        bible_reference.text()

    def add_arguments(self, parser):
        parser.add_argument('bible_id', type=str)
