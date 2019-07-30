from enum import Enum

from bible_lib import Bible
from bible_lib import BibleBooks
from django.db import models


class CommandmentCategories(Enum):
    Salvation = "Salvation commands"
    Discipleship = "Discipleship Commands"
    EffectiveWorship = "Effective worship commands"
    Blessings = "Blessings"
    JudgmentSeat = "Judgment Seat and Rewards commands"
    Relationship = "Relationship Commands"
    Marriage = "Marriage commands"
    Persecution = "Persecution Commands"
    HowToBe = "How to Be, Do or Think commands"
    EthicOfLove = "Ethic of Love"
    Prayer = "Prayer Commands"
    FalseTeachers = "False Teachers Commands"
    Evangelism = "Evangelism and Missions"
    Greatest = "Greatest Commands"
    Finance = "Finance Commands"
    EndTimes = "End Times"


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
    bible_id = 'ead7b4cc5007389c-01'  # maybe some user setting from user preferences?
    text = 'not loaded'

    class Meta:
        abstract = True

    def load_text(self):
        """Get the verse text from the bible api."""
        self.text = Bible(self.bible_id).verse(BibleBooks[self.book], self.chapter, self.verse)

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
