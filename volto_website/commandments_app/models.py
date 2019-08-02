from enum import Enum

from bible_lib import BibleFactory
from bible_lib import BibleBooks
from django.db import models
from django.utils import translation
from django.utils.translation import gettext


class CommandmentCategories(Enum):
    Salvation = gettext("Salvation commands")
    Discipleship = gettext("Discipleship Commands")
    EffectiveWorship = gettext("Effective worship commands")
    Blessings = gettext("Blessings")
    JudgmentSeat = gettext("Judgment Seat and Rewards commands")
    Relationship = gettext("Relationship Commands")
    Marriage = gettext("Marriage commands")
    Persecution = gettext("Persecution Commands")
    HowToBe = gettext("How to Be, Do or Think commands")
    EthicOfLove = gettext("Ethic of Love")
    Prayer = gettext("Prayer Commands")
    FalseTeachers = gettext("False Teachers Commands")
    Evangelism = gettext("Evangelism and Missions")
    Greatest = gettext("Greatest Commands")
    Finance = gettext("Finance Commands")
    EndTimes = gettext("End Times")


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

    def __str__(self):
        return '{} {}:{}'.format(self.book, self.chapter, self.verse)


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
