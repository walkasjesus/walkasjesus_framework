from django.conf.global_settings import LANGUAGES
from django.db import models
from sorl.thumbnail import get_thumbnail
from url_or_relative_url_field.fields import URLOrRelativeURLField

from commandments_app.models import Commandment, gettext_lazy
from jesus_commandments_website.settings import MEDIA_URL


class Media(models.Model):
    """" Abstract base class for other media models. """
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)
    title = models.CharField(max_length=128, default='', null=True, blank=True)
    description = models.TextField(default='', null=True, blank=True)
    target_audience = models.CharField(max_length=32,
                                       choices=[('any', 'any'),
                                                ('adults', 'adults'),
                                                ('kids', 'kids')],
                                       default='any')
    author = models.CharField(max_length=64, default='')
    img_url = URLOrRelativeURLField(default='', null=True, blank=True)
    url = models.URLField(max_length=300, null=True, blank=True)
    language_choices = [('any', gettext_lazy('Language independent')),
                        ('unknown', gettext_lazy('Language unknown'))]
    language_choices += LANGUAGES
    language = models.CharField(max_length=8, choices=language_choices, default='en')
    is_public = models.BooleanField(default=False)

    class Meta:
        abstract = True
        unique_together = ['commandment', 'title', 'url', 'img_url', 'author', 'language', 'target_audience']

    def __str__(self):
        return f'Media: {self.title} {self.author} {self.target_audience} {self.language} {self.img_url} {self.url}'


class Drawing(Media):
    pass

    def thumbnail_url(self):
        image_source_path = self.img_url
        # The thumbnail searches relative to the media directory so remove the leading media directory.
        if image_source_path.startswith(MEDIA_URL):
            image_source_path = image_source_path[len(MEDIA_URL):]

        thumbnail = get_thumbnail(image_source_path, '620x877', quality=85)
        return thumbnail.url


class Song(Media):
    pass


class Superbook(Media):
    pass


class Henkieshow(Media):
    pass


class Movie(Media):
    pass


class ShortMovie(Media):
    pass


class WaJVideo(Media):
    pass


class Sermon(Media):
    pass


class Picture(Media):
    pass


class Testimony(Media):
    pass


class Book(Media):
    pass


class Blog(Media):
    pass

