from django.db import models

from callings_app.lib.bible_books import BibleBooks


class Calling(models.Model):
    quote = models.CharField(max_length=256)

    def __str__(self):
        return self.quote


class BibleReference(models.Model):
    calling = models.ForeignKey(Calling, on_delete=models.CASCADE)
    book = models.CharField(max_length=32,
                            choices=[(tag.name, tag.value) for tag in BibleBooks],
                            default=BibleBooks.Genesis)
    chapter = models.IntegerField(default=1)
    verse = models.IntegerField(default=1)

    def __str__(self):
        return '{} {}:{}'.format(self.book, self.chapter, self.verse)


class Image(models.Model):
    calling = models.ForeignKey(Calling, on_delete=models.CASCADE)
    title = models.TextField()
    url = models.ImageField(upload_to='images/')

    def __str__(self):
        return self.title
