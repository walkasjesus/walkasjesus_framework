import logging
from enum import Enum

from bible_lib import BibleBooks as BibleLibBibleBooks
from bible_lib import BibleFactory, Bibles, Bible
from django.conf import settings
from django.conf.global_settings import LANGUAGES
from django.db import models
from django.utils import translation
from django.utils.translation import gettext, gettext_lazy
from url_or_relative_url_field.fields import URLOrRelativeURLField
from froala_editor.fields import FroalaField

from commandments_app.lib.ordered_enum import OrderedEnum


class Redirect(models.Model):
    url = URLOrRelativeURLField()


class CommandmentCategories(Enum):
    Salvation = gettext_lazy('Salvation Commands')
    Discipleship = gettext_lazy('Discipleship Commands')
    Worship = gettext_lazy('Worship Commands')
    Blessings = gettext_lazy('Blessings')
    JudgmentSeat = gettext_lazy('Judgment Seat Commands')
    Relationship = gettext_lazy('Relationship Commands')
    Marriage = gettext_lazy('Marriage Commands')
    Persecution = gettext_lazy('Persecution Commands')
    Thinking = gettext_lazy('Thinking Commands')
    Prayer = gettext_lazy('Prayer Commands')
    FalseTeachers = gettext_lazy('False Teachers Commands')
    Witnessing = gettext_lazy('Witnessing Commands')
    Greatest = gettext_lazy('Greatest Commands')
    Finance = gettext_lazy('Finance Commands')
    Holiness = gettext_lazy('Holiness Commands')


class BibleBooks(OrderedEnum):
    """" This is a copy of the enum in bible_lib,
    but I did not know how to tag it for translation
    without making a copy. """
    Genesis = gettext_lazy('Genesis')
    Exodus = gettext_lazy('Exodus')
    Leviticus = gettext_lazy('Leviticus')
    Numbers = gettext_lazy('Numbers')
    Deuteronomy = gettext_lazy('Deuteronomy')
    Joshua = gettext_lazy('Joshua')
    Judges = gettext_lazy('Judges')
    Ruth = gettext_lazy('Ruth')
    SamuelFirstBook = gettext_lazy('1 Samuel')
    SamuelSecondBook = gettext_lazy('2 Samuel')
    KingsFirstBook = gettext_lazy('1 Kings')
    KingsSecondBook = gettext_lazy('2 Kings')
    ChroniclesFirstBook = gettext_lazy('1 Chronicles')
    ChroniclesSecondBook = gettext_lazy('2 Chronicles')
    Ezra = gettext_lazy('Ezra')
    Nehemiah = gettext_lazy('Nehemiah')
    Esther = gettext_lazy('Esther')
    Job = gettext_lazy('Job')
    Psalms = gettext_lazy('Psalms')
    Proverbs = gettext_lazy('Proverbs')
    Ecclesiastes = gettext_lazy('Ecclesiastes')
    SongOfSolomon = gettext_lazy('Song of Solomon')
    Isaiah = gettext_lazy('Isaiah')
    Jeremiah = gettext_lazy('Jeremiah')
    Lamentations = gettext_lazy('Lamentations')
    Ezekiel = gettext_lazy('Ezekiel')
    Daniel = gettext_lazy('Daniel')
    Hosea = gettext_lazy('Hosea')
    Joel = gettext_lazy('Joel')
    Amos = gettext_lazy('Amos')
    Obadiah = gettext_lazy('Obadiah')
    Jonah = gettext_lazy('Jonah')
    Micah = gettext_lazy('Micah')
    Nahum = gettext_lazy('Nahum')
    Habakkuk = gettext_lazy('Habakkuk')
    Zephaniah = gettext_lazy('Zephaniah')
    Haggai = gettext_lazy('Haggai')
    Zechariah = gettext_lazy('Zechariah')
    Malachi = gettext_lazy('Malachi')
    Matthew = gettext_lazy('Matthew')
    Mark = gettext_lazy('Mark')
    Luke = gettext_lazy('Luke')
    John = gettext_lazy('John')
    Acts = gettext_lazy('Acts')
    Romans = gettext_lazy('Romans')
    CorinthiansFirstBook = gettext_lazy('1 Corinthians')
    CorinthiansSecondBook = gettext_lazy('2 Corinthians')
    Galatians = gettext_lazy('Galatians')
    Ephesians = gettext_lazy('Ephesians')
    Philippians = gettext_lazy('Philippians')
    Colossians = gettext_lazy('Colossians')
    ThessaloniansFirstBook = gettext_lazy('1 Thessalonians')
    ThessaloniansSecondBook = gettext_lazy('2 Thessalonians')
    TimothyFirstBook = gettext_lazy('1 Timothy')
    TimothySecondBook = gettext_lazy('2 Timothy')
    Titus = gettext_lazy('Titus')
    Philemon = gettext_lazy('Philemon')
    Hebrews = gettext_lazy('Hebrews')
    James = gettext_lazy('James')
    PeterFirstBook = gettext_lazy('1 Peter')
    PeterSecondBook = gettext_lazy('2 Peter')
    JohnFirstBook = gettext_lazy('1 John')
    JohnSecondBook = gettext_lazy('2 John')
    JohnThirdBook = gettext_lazy('3 John')
    Jude = gettext_lazy('Jude')
    Revelation = gettext_lazy('Revelation')


class Commandment(models.Model):
    title = models.CharField(max_length=256)
    title_negative = models.CharField(max_length=256, default=None, blank=True, null=True)
    devotional = FroalaField()
    devotional_source = models.CharField(max_length=256, default=None, blank=True, null=True)
    category = models.CharField(max_length=32,
                                choices=[(tag.name, tag.value) for tag in CommandmentCategories],
                                default=CommandmentCategories.Salvation)
    quote = models.TextField(default=None, blank=True, null=True)
    quote_source = models.CharField(max_length=256, default=None, blank=True, null=True)
    bible = BibleFactory().create('hsv')
    languages = [translation.get_language()]

    def primary_bible_reference(self):
        """ Primary references is the first found unique reference according to the words of Jesus,
        directly related to the commandment. """
        reference = self.primarybiblereference
        reference.set_bible(self.bible)
        return reference

    def secondary_bible_references(self):
        """ Secondary references are extra references which are related te the same priciple. """
        return self._get_translated_bible_references(self.secondarybiblereference_set.all())

    def tertiary_bible_references(self):
        """ Tertiary references are extra, maybe indirect references, also relating to the same principle. """
        return self._get_translated_bible_references(self.tertiarybiblereference_set.all())

    def background_drawing(self):
        return self.drawings()[0] if self.drawings() else ''

    def background_song(self):
        return self.songs()[0] if self.songs() else ''

    def drawings(self):
        return self.drawing_set.filter(is_public=True)

    def songs(self):
        return self._filter_on_language(self.song_set)

    def movies(self):
        return self._filter_on_language(self.movie_set)

    def short_movies(self):
        return self._filter_on_language(self.shortmovie_set)

    def sermons(self):
        return self._filter_on_language(self.sermon_set)

    def pictures(self):
        return self.picture_set.filter(is_public=True)

    def testimonies(self):
        return self._filter_on_language(self.testimony_set)

    def blogs(self):
        return self._filter_on_language(self.blog_set)

    def books(self):
        return self._filter_on_language(self.book_set)

    def questions(self):
        return self.question_set.all()

    def _filter_on_language(self, query):
        return query.filter(language__in=self.languages, is_public=True)

    def _get_translated_bible_references(self, query_set):
        [ref.set_bible(self.bible) for ref in query_set]
        return query_set

    def __str__(self):
        return self.title


class UserPreferences:
    def __init__(self, session):
        self.session = session

    @property
    def bible(self):
        if 'bible_id' in self.session:
            return BibleFactory().create(self.session['bible_id'])

        if self.language == 'nl':
            return BibleFactory().create('hsv')

        return BibleFactory().create('de4e12af7f28f599-01')

    @bible.setter
    def bible(self, value):
        self.session['bible_id'] = value.id

    @property
    def language(self):
        return translation.get_language()

    @property
    def languages(self):
        """ A user can select multiple languages (so more media is shown for example)"""
        if 'languages' in self.session and self.session['languages'] is not None:
            return self.session['languages']

        # If nothing is specified, default to user main language
        return [self.language]

    @languages.setter
    def languages(self, value) -> []:
        # Sort so when using in comparison or cache key [en, nl] is the same cache as [nl, en]
        self.session['languages'] = sorted(value)


class BibleTranslation:
    bibles = Bibles()

    def all(self) -> [Bible]:
        return self.bibles.list()

    def all_in_user_language(self) -> [Bible]:
        current_user_language = translation.get_language()
        return [b for b in self.all() if b.language == current_user_language]

    def all_in_supported_languages(self):
        languages = [code for code, name in settings.LANGUAGES]
        return [b for b in self.all() if b.language in languages]


class AbstractBibleReference(models.Model):
    book = models.CharField(max_length=32,
                            choices=[(tag.name, tag.value) for tag in BibleBooks],
                            default=BibleBooks.Genesis)
    begin_chapter = models.IntegerField(default=1)
    begin_verse = models.IntegerField(default=1)
    end_chapter = models.IntegerField(default=0)
    end_verse = models.IntegerField(default=0)
    bible = BibleFactory().create('hsv')

    class Meta:
        abstract = True

    def set_bible(self, bible: Bible):
        """ Set a bible to get the text in that bible translation."""
        self.bible = bible

    def text(self):
        """Get the verse text from the bible api."""
        if self.end_chapter == 0:
            end_chapter = self.begin_chapter
        else:
            end_chapter = self.end_chapter

        if self.end_verse == 0:
            end_verse = self.begin_verse
        else:
            end_verse = self.end_verse

        try:
            # Here we run into a bit of code smell, we do not use the enum provided by bible_lib,
            # As we want to translate the enum values. However before sending a query we convert to the bible_lib enum.
            return self.bible.verses(BibleLibBibleBooks[self.book],
                                     self.begin_chapter,
                                     self.begin_verse,
                                     end_chapter,
                                     end_verse)

        except Exception as ex:
            logging.getLogger().warning('Failed to load bible text')
            logging.getLogger().exception(ex)

        return gettext('Could not load text at the moment.')

    def __str__(self):
        book_chapter_verse = f'{self.get_book_display()} {self.begin_chapter}:{self.begin_verse}'

        if self.begin_chapter == 0 or self.end_verse == 0:
            return book_chapter_verse

        if self.begin_chapter == self.end_chapter and self.begin_verse == self.end_verse:
            return book_chapter_verse

        if self.begin_chapter == self.end_chapter and self.end_verse > self.begin_verse:
            return f'{book_chapter_verse}-{self.end_verse}'

        return f'{book_chapter_verse}-{self.end_chapter}:{self.end_verse}'

    def __lt__(self, other):
        if self.__class__ is not other.__class__:
            return NotImplemented

        if BibleBooks[self.book] < BibleBooks[other.book]:
            return True

        if BibleBooks[self.book] == BibleBooks[other.book] and self.begin_chapter < self.begin_chapter:
            return True

        if BibleBooks[self.book] == BibleBooks[other.book] and \
                self.begin_chapter == self.begin_chapter and \
                self.begin_verse < self.begin_verse:
            return True

        return False


class PrimaryBibleReference(AbstractBibleReference):
    commandment = models.OneToOneField(Commandment, on_delete=models.CASCADE)


class SecondaryBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)


class TertiaryBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)


class BibleReferences:
    def __init__(self):
        self.bible = BibleFactory().create('hsv')
        self._data = None

    def primary(self):
        return self._query_references(PrimaryBibleReference.objects.filter(commandment__gt=0))

    def secondary(self):
        return self._query_references(SecondaryBibleReference.objects.filter(commandment__gt=0))

    def tertiary(self):
        return self._query_references(TertiaryBibleReference.objects.filter(commandment__gt=0))

    def _query_references(self, query):
        # This will reduce the amount of sql queries as we already know we also want the commandments
        query = query.select_related()

        # Set the bible for each reference
        [ref.set_bible(self.bible) for ref in query]

        return query


class Media(models.Model):
    """" Abstract base class for other media models. """
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)
    title = models.CharField(max_length=128, default='')
    description = models.TextField(default='')
    author = models.CharField(max_length=64, default='')
    url = URLOrRelativeURLField(default='#')
    language = models.CharField(max_length=8, choices=LANGUAGES, default='en')
    is_public = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __str__(self):
        return f'Media at: {self.url}'


class Drawing(Media):
    pass


class Song(Media):
    pass


class Movie(Media):
    pass


class ShortMovie(Media):
    pass


class Sermon(Media):
    pass


class Picture(Media):
    pass


class Testimony(Media):
    pass


class Blog(Media):
    pass


class Book(Media):
    pass


class File(models.Model):
    title = models.CharField(max_length=128, default='')
    file = models.ImageField(upload_to='files/')

    def __str__(self):
        return self.title


class Question(models.Model):
    """" Abstract base class for other media models. """
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)
    text = models.TextField(default='')

    def __str__(self):
        return self.text
