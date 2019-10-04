import logging

from bible_lib import BibleFactory, Bible
from django.utils import translation
from hsv_bible_lib import HsvBible

from jesus_commandments_website import settings


class CombinedBiblesFactory:
    """" Used to combine all bibles from multiple libraries. """
    hsv_bible = None

    def __init__(self):
        self.api_bible_factory = BibleFactory(settings.BIBLE_API_KEY)
        if CombinedBiblesFactory.hsv_bible is None:
            try:
                CombinedBiblesFactory.hsv_bible = HsvBible(settings.HSV_BIBLE_KEY, settings.HSV_BIBLE_PATH)
            except Exception as ex:
                logging.getLogger().warning(f'Failed to initialize HsvBible. {ex}')

    def all(self):
        bibles = self.api_bible_factory.all()
        bibles['hsv'] = CombinedBiblesFactory.hsv_bible

        return bibles

    def get(self, bible_id: str):
        """" Get a specific bible translation given its unique id. """
        if bible_id not in self.all():
            logging.getLogger().warning(f'Could not find bible with id {bible_id}')
        else:
            return self.all()[bible_id]


class BibleTranslation:
    """" Get a specific (set of) bible translation(s). """
    _all_bibles = None

    def all(self) -> [Bible]:
        """" Get all bible translations (including languages not supported this website). """
        if self._all_bibles is None:
            _all_bibles = list(CombinedBiblesFactory().all().values())

        return _all_bibles

    def all_in_user_language(self) -> [Bible]:
        """" Get all bibles in the user main language. """
        current_user_language = translation.get_language()
        return [b for b in self.all() if b.language == current_user_language]

    def all_in_supported_languages(self):
        """" Get all bibles in translations supported by this website. """
        languages = [code for code, name in settings.LANGUAGES]
        return [b for b in self.all() if b.language in languages]

    def get(self, bible_id: str):
        """" Get a specific bible translation given its unique id. """
        return CombinedBiblesFactory().get(bible_id)
