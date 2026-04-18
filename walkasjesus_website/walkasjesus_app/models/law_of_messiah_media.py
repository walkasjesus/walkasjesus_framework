from django.conf.global_settings import LANGUAGES
from django.db import models
from sorl.thumbnail import get_thumbnail
from url_or_relative_url_field.fields import URLOrRelativeURLField

from django.utils.translation import gettext_lazy
from .law_of_messiah import LawOfMessiah
from walkasjesus_website.settings import MEDIA_URL


class LawOfMessiahMedia(models.Model):
    """Abstract base class for Law of Messiah media models."""
    law_of_messiah = models.ForeignKey(
        LawOfMessiah,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name='media'
    )
    title = models.CharField(max_length=128, default='', null=True, blank=True)
    description = models.TextField(default='', null=True, blank=True)
    target_audience = models.CharField(
        max_length=32,
        choices=[('any', 'any'), ('adults', 'adults'), ('kids', 'kids')],
        default='any'
    )
    author = models.CharField(max_length=64, default='')
    img_url = URLOrRelativeURLField(default='', null=True, blank=True)
    url = models.URLField(max_length=300, null=True, blank=True)
    language_choices = [
        ('any', gettext_lazy('Language independent')),
        ('unknown', gettext_lazy('Language unknown'))
    ]
    language_choices += LANGUAGES
    language = models.CharField(max_length=8, choices=language_choices, default='en')
    is_public = models.BooleanField(default=False)

    class Meta:
        abstract = True
        unique_together = ['law_of_messiah', 'title', 'url', 'img_url', 'author', 'language', 'target_audience']

    def __str__(self):
        return f'Media: {self.title} {self.author} {self.target_audience} {self.language} {self.img_url} {self.url}'


class LawOfMessiahDrawing(LawOfMessiahMedia):
    """Drawing media for Law of Messiah items."""

    def thumbnail_url(self):
        image_source_path = self.img_url
        # The thumbnail searches relative to the media directory so remove the leading media directory.
        if image_source_path.startswith(MEDIA_URL):
            image_source_path = image_source_path[len(MEDIA_URL):]

        thumbnail = get_thumbnail(image_source_path, '620x877', quality=85)
        return thumbnail.url
