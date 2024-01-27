import re
from django.conf.global_settings import LANGUAGES
from django.db import models
from sorl.thumbnail import get_thumbnail
from url_or_relative_url_field.fields import URLOrRelativeURLField

from commandments_app.models import Lesson, gettext_lazy
from jesus_commandments_website.settings import MEDIA_URL


class LessonMedia(models.Model):
    """ Abstract base class for other media models. """
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True, default=None)
    title = models.CharField(max_length=128, default='', null=True, blank=True)
    description = models.TextField(default='', null=True, blank=True)
    target_audience = models.CharField(max_length=32,
                                       choices=[('any', 'any'),
                                                ('adults', 'adults'),
                                                ('kids', 'kids')],
                                       default='kids')
    author = models.CharField(max_length=64, default='')
    img_url = URLOrRelativeURLField(default='', null=True, blank=True)
    url = models.URLField(max_length=300, null=True, blank=True)
    language_choices = [('any', gettext_lazy('Language independent')),
                        ('unknown', gettext_lazy('Language unknown'))]
    language_choices += LANGUAGES
    language = models.CharField(max_length=8, choices=language_choices, default='nl')
    is_public = models.BooleanField(default=True)

    class Meta:
        abstract = True
        unique_together = ['lesson', 'title', 'url', 'img_url', 'author', 'language', 'target_audience']

    def convert_youtube_url(self, url):
        """
        Convert YouTube video URL to embedded format.
        """
        # Regular expressions for parsing YouTube URLs
        youtube_regex = r"^(https?://)?(www\.)?(youtube\.com/watch\?[^/]*?v=|youtu\.be/|youtube-nocookie\.com/embed/)" \
                        r"([^&=%\?]{11})"
        youtube_oembed_regex = r"^(https?://)?(www\.)?youtube\.com/oembed.*?url=(https?://www\.youtube\.com/watch[^&]*)"

        # Check if the URL matches any of the YouTube URL patterns
        print("Input URL:", url)
        match = re.match(youtube_regex, url)
        if match:
            print("Matched youtube_regex")
            # Extract video ID from the URL
            video_id = match.group(4)
            print("Extracted Video ID:", video_id)
            return f"https://www.youtube.com/embed/{video_id}"
        elif re.match(youtube_oembed_regex, url):
            print("Matched youtube_oembed_regex")
            # Extract video ID from the oEmbed URL
            video_id_match = re.search(r"([^&=%\?]{11})", url)
            if video_id_match:
                video_id = video_id_match.group(0)
                print("Extracted Video ID:", video_id)
                return f"https://www.youtube.com/embed/{video_id}"

        print("No match found, returning original URL")
        return url
    def save(self, *args, **kwargs):
        # Convert YouTube URL to embedded format if it's a YouTube video
        if self.url:
            self.url = self.convert_youtube_url(self.url)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Media: {self.title} {self.author} {self.target_audience} {self.language} {self.img_url} {self.url}'


class LessonDrawing(LessonMedia):
    pass

    def thumbnail_url(self):
        image_source_path = self.img_url
        # The thumbnail searches relative to the media directory so remove the leading media directory.
        if image_source_path.startswith(MEDIA_URL):
            image_source_path = image_source_path[len(MEDIA_URL):]

        thumbnail = get_thumbnail(image_source_path, '620x877', quality=85)
        return thumbnail.url


class LessonSong(LessonMedia):
    pass


class LessonSuperbook(LessonMedia):
    pass


class LessonHenkieshow(LessonMedia):
    pass


class LessonShortMovie(LessonMedia):
    pass


class LessonPicture(LessonMedia):
    pass


class LessonTestimony(LessonMedia):
    pass

