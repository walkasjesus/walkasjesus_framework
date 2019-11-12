import logging

from bible_lib import BibleFactory, Bible
from django.utils import translation
from hsv_bible_lib import HsvBible
from django.db import models
from jesus_commandments_website import settings


class CombinedBiblesFactory:
    """" Used to combine all bibles from multiple libraries. """
    hsv_bible = None

    def __init__(self):
        try:
            self.hsv_supported = (settings.HSV_BIBLE_KEY != '' and settings.HSV_BIBLE_PATH != '')
        except:
            self.hsv_supported = False

        self.api_bible_factory = BibleFactory(settings.BIBLE_API_KEY)
        if self.hsv_supported and CombinedBiblesFactory.hsv_bible is None:
            try:
                hsv = HsvBible(settings.HSV_BIBLE_KEY, settings.HSV_BIBLE_PATH)
                CombinedBiblesFactory.hsv_bible = hsv
            except Exception as ex:
                logging.getLogger().warning(f'Failed to initialize HsvBible. {ex}')

    def all(self):
        bibles = self.api_bible_factory.all()

        if self.hsv_supported and CombinedBiblesFactory.hsv_bible is not None:
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
    _all_bibles = CombinedBiblesFactory().all()

    def all(self) -> [Bible]:
        """" Get all bible translations (including languages not supported this website). """
        return list(BibleTranslation._all_bibles.values())

    def all_enabled(self) -> [Bible]:
        """ This will list all bibles that are not explicitly disabled,
        so if information is missing it will assume them to be enabled. """
        return set(self.all()) - set(self.all_disabled())

    def all_disabled(self) -> [Bible]:
        """ This will return all bibles that are explicitly disabled. """
        return [CombinedBiblesFactory().get(m.bible_id)
                for m in BibleTranslationMetaData.objects.all()
                if m.is_enabled is False]

    def all_in_user_language(self) -> [Bible]:
        """" Get all bibles in the user main language. """
        current_user_language = translation.get_language()
        return [b for b in self.all_enabled() if b.language == current_user_language]

    def all_in_supported_languages(self):
        """" Get all bibles in translations supported by this website. """
        languages = [code for code, name in settings.LANGUAGES]
        return [b for b in self.all_enabled() if b.language in languages]

    def count(self):
        return len(self.all_enabled())

    def get(self, bible_id: str):
        """" Get a specific bible translation given its unique id. """
        return BibleTranslation._all_bibles[bible_id]

    def contains(self, bible_id: str):
        return bible_id in BibleTranslation._all_bibles


class BibleTranslationMetaData(models.Model):
    """ While the BibleTranslation itself is dynamically retrieved from the library,
    we want some extra information stored in the database, like if we want to enable it or not. """
    bible_id = models.CharField(max_length=32, unique=True, null=False, default='')
    is_enabled = models.BooleanField(default=True)
