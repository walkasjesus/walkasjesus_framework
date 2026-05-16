from django.conf.global_settings import LANGUAGES
from django.db import models
from sorl.thumbnail import get_thumbnail
from url_or_relative_url_field.fields import URLOrRelativeURLField

from django.utils.translation import gettext_lazy
from .law_of_messiah import LawOfMessiah
from walkasjesus_website.settings import MEDIA_URL


class LawOfMessiahMedia(models.Model):
    """Abstract base class for Law of Messiah media models."""
    MEDIA_TYPE_DRAWING = 'drawing'
    MEDIA_TYPE_SONG = 'song'
    MEDIA_TYPE_SUPERBOOK = 'superbook'
    MEDIA_TYPE_HENKIESHOW = 'henkieshow'
    MEDIA_TYPE_MOVIE = 'movie'
    MEDIA_TYPE_SHORTMOVIE = 'shortmovie'
    MEDIA_TYPE_WAJVIDEO = 'wajvideo'
    MEDIA_TYPE_SERMON = 'sermon'
    MEDIA_TYPE_PICTURE = 'picture'
    MEDIA_TYPE_TESTIMONY = 'testimony'
    MEDIA_TYPE_BLOG = 'blog'
    MEDIA_TYPE_BOOK = 'book'
    MEDIA_TYPE_CHOICES = [
        (MEDIA_TYPE_DRAWING, 'Drawing'),
        (MEDIA_TYPE_SONG, 'Song'),
        (MEDIA_TYPE_SUPERBOOK, 'Superbook'),
        (MEDIA_TYPE_HENKIESHOW, 'Henkieshow'),
        (MEDIA_TYPE_MOVIE, 'Movie'),
        (MEDIA_TYPE_SHORTMOVIE, 'ShortMovie'),
        (MEDIA_TYPE_WAJVIDEO, 'WaJVideo'),
        (MEDIA_TYPE_SERMON, 'Sermon'),
        (MEDIA_TYPE_PICTURE, 'Picture'),
        (MEDIA_TYPE_TESTIMONY, 'Testimony'),
        (MEDIA_TYPE_BLOG, 'Blog'),
        (MEDIA_TYPE_BOOK, 'Book'),
    ]

    law_of_messiah = models.ForeignKey(
        LawOfMessiah,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name='media'
    )
    commandment = models.ForeignKey(
        'Commandment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name='shared_media_resources',
    )
    lesson = models.ForeignKey(
        'Lesson',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        default=None,
        related_name='shared_media_resources',
    )
    title = models.CharField(max_length=128, default='', null=True, blank=True)
    description = models.TextField(default='', null=True, blank=True)
    media_type = models.CharField(max_length=32, choices=MEDIA_TYPE_CHOICES, default=MEDIA_TYPE_DRAWING)
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
        unique_together = [
            'law_of_messiah',
            'commandment',
            'lesson',
            'media_type',
            'title',
            'url',
            'img_url',
            'author',
            'language',
            'target_audience',
        ]

    def __str__(self):
        return f'Media: {self.title} {self.author} {self.target_audience} {self.language} {self.img_url} {self.url}'


class LawOfMessiahDrawing(LawOfMessiahMedia):
    """Drawing media for Law of Messiah items."""

    def thumbnail_url(self):
        image_source_path = (self.img_url or '').strip()
        # The thumbnail storage is rooted at MEDIA_ROOT, so normalize to a path relative to it.
        if image_source_path.startswith(MEDIA_URL):
            image_source_path = image_source_path[len(MEDIA_URL):]
        if image_source_path.startswith('/'):
            image_source_path = image_source_path[1:]
        if image_source_path.startswith('media/'):
            image_source_path = image_source_path[len('media/'):]

        thumbnail = get_thumbnail(image_source_path, '620x877', quality=85)
        return thumbnail.url


class MediaResource(LawOfMessiahDrawing):
    class Meta:
        proxy = True
        verbose_name = 'Media Resource'
        verbose_name_plural = 'Media Resources'
