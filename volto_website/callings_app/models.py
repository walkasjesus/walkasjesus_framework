from django.db import models


class Calling(models.Model):
    quote = models.CharField(max_length=256)

    def __str__(self):
        return self.quote


class BibleReference(models.Model):
    calling = models.ForeignKey(Calling, on_delete=models.CASCADE)
    book = models.CharField(max_length=32)
    chapter = models.IntegerField(default=1)
    verse = models.IntegerField(default=1)
