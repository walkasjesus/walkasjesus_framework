from enum import Enum

from bible_lib import BibleFactory
from django.db import models
from django.utils import translation
from django.utils.translation import gettext


class CommandmentCategories(Enum):
    Salvation = gettext('Salvation commands')
    Discipleship = gettext('Discipleship Commands')
    EffectiveWorship = gettext('Effective worship commands')
    Blessings = gettext('Blessings')
    JudgmentSeat = gettext('Judgment Seat and Rewards commands')
    Relationship = gettext('Relationship Commands')
    Marriage = gettext('Marriage commands')
    Persecution = gettext('Persecution Commands')
    HowToBe = gettext('How to Be, Do or Think commands')
    EthicOfLove = gettext('Ethic of Love')
    Prayer = gettext('Prayer Commands')
    FalseTeachers = gettext('False Teachers Commands')
    Evangelism = gettext('Evangelism and Missions')
    Greatest = gettext('Greatest Commands')
    Finance = gettext('Finance Commands')
    EndTimes = gettext('End Times')
    

class BibleBooks(Enum):
    """" This is a copy of the enum in bible_lib,
    but I did not know how to tag it for translation
    without making a copy. """
    Genesis = gettext('Genesis')
    Exodus = gettext('Exodus')
    Leviticus = gettext('Leviticus')
    Numbers = gettext('Numbers')
    Deuteronomy = gettext('Deuteronomy')
    Joshua = gettext('Joshua')
    Judges = gettext('Judges')
    Ruth = gettext('Ruth')
    SamuelFirstBook = gettext('1 Samuel')
    SamuelSecondBook = gettext('2 Samuel')
    KingsFirstBook = gettext('1 Kings')
    KingsSecondBook = gettext('2 Kings')
    ChroniclesFirstBook = gettext('1 Chronicles')
    ChroniclesSecondBook = gettext('2 Chronicles')
    Ezra = gettext('Ezra')
    Nehemiah = gettext('Nehemiah')
    Esther = gettext('Esther')
    Job = gettext('Job')
    Psalms = gettext('Psalms')
    Proverbs = gettext('Proverbs')
    Ecclesiastes = gettext('Ecclesiastes')
    SongOfSolomon = gettext('Song of Solomon')
    Isaiah = gettext('Isaiah')
    Jeremiah = gettext('Jeremiah')
    Lamentations = gettext('Lamentations')
    Ezekiel = gettext('Ezekiel')
    Daniel = gettext('Daniel')
    Hosea = gettext('Hosea')
    Joel = gettext('Joel')
    Amos = gettext('Amos')
    Obadiah = gettext('Obadiah')
    Jonah = gettext('Jonah')
    Micah = gettext('Micah')
    Nahum = gettext('Nahum')
    Habakkuk = gettext('Habakkuk')
    Zephaniah = gettext('Zephaniah')
    Haggai = gettext('Haggai')
    Zechariah = gettext('Zechariah')
    Malachi = gettext('Malachi')
    Matthew = gettext('Matthew')
    Mark = gettext('Mark')
    Luke = gettext('Luke')
    John = gettext('John')
    Acts = gettext('Acts (of the Apostles)')
    Romans = gettext('Romans')
    CorinthiansFirstBook = gettext('1 Corinthians')
    CorinthiansSecondBook = gettext('2 Corinthians')
    Galatians = gettext('Galatians')
    Ephesians = gettext('Ephesians')
    Philippians = gettext('Philippians')
    Colossians = gettext('Colossians')
    ThessaloniansFirstBook = gettext('1 Thessalonians')
    ThessaloniansSecondBook = gettext('2 Thessalonians')
    TimothyFirstBook = gettext('1 Timothy')
    TimothySecondBook = gettext('2 Timothy')
    Titus = gettext('Titus')
    Philemon = gettext('Philemon')
    Hebrews = gettext('Hebrews')
    James = gettext('James')
    PeterFirstBook = gettext('1 Peter')
    PeterSecondBook = gettext('2 Peter')
    JohnFirstBook = gettext('1 John')
    JohnSecondBook = gettext('2 John')
    JohnThirdBook = gettext('3 John')
    Jude = gettext('Jude')
    Revelation = gettext('Revelation')


class Commandment(models.Model):
    title = models.CharField(max_length=256)
    description = models.TextField(default='')
    category = models.CharField(max_length=32,
                                choices=[(tag.name, tag.value) for tag in CommandmentCategories],
                                default=CommandmentCategories.Salvation)

    def primary_bible_references(self):
        """ Primary references are the most important references, directly related to the commandment. """
        return self.primarybiblereference_set.all()

    def secondary_bible_references(self):
        """ Secondary references are extra, maybe indirect references. """
        return self.secondarybiblereference_set.all()

    def images(self):
        return self.image_set.filter(is_public=True)

    def songs(self):
        return self.song_set.filter(is_public=True)

    def sermons(self):
        return self.sermon_set.filter(is_public=True)

    def __str__(self):
        return self.title


class AbstractBibleReference(models.Model):
    book = models.CharField(max_length=32,
                            choices=[(tag.name, tag.value) for tag in BibleBooks],
                            default=BibleBooks.Genesis)
    chapter = models.IntegerField(default=1)
    verse = models.IntegerField(default=1)
    text = gettext('Could not load text at the moment.')

    class Meta:
        abstract = True

    def bible_id(self):
        current_user_language = translation.get_language()

        if current_user_language == 'nl':
            return 'hsv'

        if current_user_language == 'en':
            return 'de4e12af7f28f599-01'

        return 'de4e12af7f28f599-01'

    def load_text(self):
        """Get the verse text from the bible api."""
        self.text = BibleFactory().create(self.bible_id()).verse(BibleBooks[self.book], self.chapter, self.verse)

    def book_name(self):
        return gettext(BibleBooks[self.book].value)

    def __str__(self):
        return f'{self.book_name()} {self.chapter}:{self.verse}'


class PrimaryBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)


class SecondaryBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)


class Media(models.Model):
    """" Abstract base class for other media models. """
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)
    title = models.TextField()
    is_public = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __str__(self):
        return self.title


class Image(Media):
    file = models.ImageField(upload_to='images/')


class Song(Media):
    file = models.FileField(upload_to='songs/')


class Sermon(Media):
    file = models.FileField(upload_to='sermons/')


class File(Media):
    file = models.ImageField(upload_to='files/')
