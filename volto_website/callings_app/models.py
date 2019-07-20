from django.db import models

from callings_app.lib.bible_books import BibleBooks


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

    class Meta:
        abstract = True

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
