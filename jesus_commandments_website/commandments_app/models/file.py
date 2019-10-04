from django.db import models


class File(models.Model):
    title = models.CharField(max_length=128, default='')
    file = models.ImageField(upload_to='files/')

    def __str__(self):
        return self.title
