import logging

from bible_lib import BibleFactory, Bible
from django.db import models
from django.utils import translation

from jesus_commandments_website import settings


class BibleTranslation:
    """" Get a specific (set of) bible translation(s). """
    _bible_factory = BibleFactory(settings.BIBLE_API_KEY)
    _all_bibles = _bible_factory.all()

    def all(self) -> [Bible]:
        """" Get all bible translations (including languages not supported this website). """
        return list(BibleTranslation._all_bibles.values())

    def all_enabled(self) -> [Bible]:
        """ This will list all bibles that are not explicitly disabled,
        so if information is missing it will assume them to be enabled. """
        return set(self.all()) - set(self.all_disabled())

    def all_disabled(self) -> [Bible]:
        """ This will return all bibles that are explicitly disabled. """
        return [BibleTranslation._bible_factory.create(m.bible_id)
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
        if bible_id not in BibleTranslation._all_bibles:
            logging.getLogger().warning(f'Failed to retrieve bible with id {bible_id}.')
            return Bible("no bible found")
        else:
            return BibleTranslation._all_bibles[bible_id]

    def contains(self, bible_id: str):
        return bible_id in BibleTranslation._all_bibles


class BibleTranslationMetaData(models.Model):
    """ While the BibleTranslation itself is dynamically retrieved from the library,
    we want some extra information stored in the database, like if we want to enable it or not. """
    bible_id = models.CharField(max_length=32, unique=True, null=False, default='')
    is_enabled = models.BooleanField(default=True)
