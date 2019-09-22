import json
from unittest import TestCase, skip

from bible_lib.bible_api.api_bible import ApiBible
from bible_lib.bible_api.bible_api_client import BibleApiClient
from bible_lib.bible_api.query_builder import QueryBuilder
from bible_lib.bible_books import BibleBooks
from bible_lib.tests.dummy_responses import DummyResponses


@skip('Only used for development')
class ManualQueriesTest(TestCase):
    def test_list_books(self):
        response_string = DummyResponses().books()
        books = json.loads(response_string)['data']
        for book in books:
            print(book['id'])

    def test_verse(self):
        bible = ApiBible('ead7b4cc5007389c-01')
        verse = bible.verse(BibleBooks.Genesis, 2, 12)
        print(verse)

    def test_query(self):
        url = QueryBuilder().get_verses('ead7b4cc5007389c-01', BibleBooks.John, 1, 51, 2, 1)

        response_string = BibleApiClient().get(url)
        print(response_string)
        # {"data":{"id":"GEN.1.1-GEN.1.2","orgId":"GEN.1.1-GEN.1.2","bibleId":"ead7b4cc5007389c-01","bookId":"GEN","chapterIds":["GEN.1"],"reference":"Genesis 1:1-2","content":[{"name":"para","type":"tag","attrs":{"style":"p"},"items":[{"name":"verse","type":"tag","attrs":{"number":"1","style":"v"},"items":[{"text":"1","type":"text"}]},{"text":"In het begin schiep God hemel en aarde. ","type":"text","attrs":{"verseId":"GEN.1.1","verseOrgIds":["GEN.1.1"]}},{"name":"verse","type":"tag","attrs":{"number":"2","style":"v"},"items":[{"text":"2","type":"text"}]},{"text":"Maar de aarde was nog ongeordend en leeg, over de wereldzee heerste duisternis, en Gods Geest zweefde over de wateren. ","type":"text","attrs":{"verseId":"GEN.1.2","verseOrgIds":["GEN.1.2"]}}]}],"copyright":"PUBLIC DOMAIN"},"meta":{"fums":"<script>\nvar _BAPI=_BAPI||{};\nif(typeof(_BAPI.t)==='undefined'){\ndocument.write('\\x3Cscript src=\"'+document.location.protocol+'//cdn.scripture.api.bible/fums/fumsv2.min.js\"\\x3E\\x3C/script\\x3E');}\ndocument.write(\"\\x3Cscript\\x3E_BAPI.t('' + unique + '');\\x3C/script\\x3E\");\n</script><noscript><img src=\"https://d3a2okcloueqyx.cloudfront.net/nf1?t=' + unique + '\" height=\"1\" width=\"1\" border=\"0\" alt=\"\" style=\"height: 0; width: 0;\" /></noscript>","fumsId":"c7044699-61ca-4bfc-9443-40198e69a13e","fumsJsInclude":"cdn.scripture.api.bible/fums/fumsv2.min.js","fumsJs":"var _BAPI=_BAPI||{};if(typeof(_BAPI.t)!='undefined'){ _BAPI.t('c7044699-61ca-4bfc-9443-40198e69a13e'); }","fumsNoScript":"<img src=\"https://d3btgtzu3ctdwx.cloudfront.net/nf1?t=c7044699-61ca-4bfc-9443-40198e69a13e\" height=\"1\" width=\"1\" border=\"0\" alt=\"\" style=\"height: 0; width: 0;\" />"}}
        entries = json.loads(response_string)['data']
        self.assertTrue(True)

    def test_find_bibles_using_alternative_daniel_key(self):
        """" Some bibles on the api use DAN instead of DAG.. """
        response_string = DummyResponses().bibles()
        bibles = json.loads(response_string)['data']
        for bible in bibles:
            id = bible['id']
            # The following line already takes care of of translating the key for bible ids
            # that we already know to use something else
            url = QueryBuilder().get_verses(id, BibleBooks.Daniel, 1, 51, 2, 1)

            try:
                BibleApiClient().get(url)
            except:
                print(f'{id} uses an alternative key or does not include Daniel (can be NT only)')
