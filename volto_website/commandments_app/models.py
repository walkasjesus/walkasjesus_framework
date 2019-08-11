from enum import Enum

from bible_lib import BibleFactory
from django.db import models
from django.utils import translation
from django.utils.translation import gettext, gettext_lazy


class CommandmentCategories(Enum):
    Salvation = gettext_lazy('Salvation commands')
    Discipleship = gettext_lazy('Discipleship Commands')
    EffectiveWorship = gettext_lazy('Effective worship commands')
    Blessings = gettext_lazy('Blessings')
    JudgmentSeat = gettext_lazy('Judgment Seat and Rewards commands')
    Relationship = gettext_lazy('Relationship Commands')
    Marriage = gettext_lazy('Marriage commands')
    Persecution = gettext_lazy('Persecution Commands')
    HowToBe = gettext_lazy('How to Be, Do or Think commands')
    EthicOfLove = gettext_lazy('Ethic of Love')
    Prayer = gettext_lazy('Prayer Commands')
    FalseTeachers = gettext_lazy('False Teachers Commands')
    Evangelism = gettext_lazy('Evangelism and Missions')
    Greatest = gettext_lazy('Greatest Commands')
    Finance = gettext_lazy('Finance Commands')
    EndTimes = gettext_lazy('End Times')


class BibleBooks(Enum):
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
    Acts = gettext_lazy('Acts (of the Apostles)')
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

    def videos(self):
        return self.video_set.filter(is_public=True)

    def sermons(self):
        return self.sermon_set.filter(is_public=True)

    def testimonies(self):
        return self.testimony_set.filter(is_public=True)

    def questions(self):
        return self.question_set.all()

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
        return gettext_lazy(BibleBooks[self.book].value)

    def __str__(self):
        return f'{self.book_name()} {self.chapter}:{self.verse}'


class PrimaryBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)


class SecondaryBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)


class Media(models.Model):
    """" Abstract base class for other media models. """
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)
    title = models.CharField(max_length=128, default='')
    author = models.CharField(max_length=64, default='')
    url = models.URLField(default='#')
    is_public = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __str__(self):
        return self.title


class Image(Media):
    pass


class Song(Media):
    pass


class Video(Media):
    pass


class Sermon(Media):
    pass


class Testimony(Media):
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
