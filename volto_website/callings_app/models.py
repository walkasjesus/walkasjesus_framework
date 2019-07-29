from bible_lib import Bible
from bible_lib import BibleBooks
from django.db import models


class Calling(models.Model):
    quote = models.CharField(max_length=256)
    description = models.TextField(default='')

    def bible_references(self):
        return self.secondarybiblereference_set.all()

    def images(self):
        return self.image_set.filter(is_public=True)

    def songs(self):
        return self.song_set.filter(is_public=True)

    def sermons(self):
        return self.sermon_set.filter(is_public=True)

    def __str__(self):
        return self.quote


class AbstractBibleReference(models.Model):
    book = models.CharField(max_length=32,
                            choices=[(tag.name, tag.value) for tag in BibleBooks],
                            default=BibleBooks.Genesis)
    chapter = models.IntegerField(default=1)
    verse = models.IntegerField(default=1)
    bible_id = 'ead7b4cc5007389c-01' # maybe some user setting from user preferences?
    text = 'not loaded'

    class Meta:
        abstract = True

    def load_text(self):
        """Get the verse text from the bible api."""
        self.text = Bible(self.bible_id).verse(BibleBooks[self.book], self.chapter, self.verse)

    def __str__(self):
        return '{} {}:{}'.format(self.book, self.chapter, self.verse)


class PrimaryBibleReference(AbstractBibleReference):
    calling = models.OneToOneField(Calling, on_delete=models.CASCADE)


class SecondaryBibleReference(AbstractBibleReference):
    calling = models.ForeignKey(Calling, on_delete=models.CASCADE)


class Media(models.Model):
    """" Abstract base class for other media models. """
    calling = models.ForeignKey(Calling, on_delete=models.CASCADE)
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
