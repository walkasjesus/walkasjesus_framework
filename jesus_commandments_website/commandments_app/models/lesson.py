from django.db import models
from django.utils import translation

from commandments_app.models import LessonCategories


class LessonManager(models.Manager):
    def with_background(self):
        """
        Allow to use Lesson.objects.with_background(),
        this is the same as Lesson.objects.all(),
        but it preloads the drawings therefor reducing the number of queries
        (at least it reduces queries if we do need the drawings)
        """
        return (c for c in Lesson.objects.all().prefetch_related('drawing_set') if c.background_drawing())


class Lesson(models.Model):
    """
    A lesson is a bit similar to a commandment,
    a lesson can cover a commandment, but this is not a requirement.
    """
    title = models.CharField(max_length=256, help_text="The title of the lesson")
    # The lesson is about these Bible books, this can be text only
    biblebooks = models.CharField(max_length=256)
    category = models.CharField(max_length=64,
                                choices=[(tag.name, tag.value) for tag in LessonCategories],
                                default=LessonCategories.oldtestament)
    bible = None
    languages = [translation.get_language()]
    objects = LessonManager()

    def primary_bible_reference(self):
        """ Primary references is the first found unique reference according to the words of Jesus,
        directly related to the commandment. """
        reference = self.primarybiblereference_set.first()
        if reference:
            reference.set_bible(self.bible)
        return reference

    def direct_bible_references(self):
        """ Extra direct Bible references which expands or explain the same commandment. """
        return self._get_translated_bible_references(self.directbiblereference_set.all())

    def background_drawing(self):
        return self.drawings()[0] if self.drawings() else ''

    def background_song(self):
        return self.songs()[0] if self.songs() else ''

    def found_superbook(self):
        return self.superbooks()[0] if self.superbooks() else ''

    def found_henkieshow(self):
        return self.henkieshows()[0] if self.henkieshows() else ''

    def drawings(self):
        # This is actually faster than filter in in the query,
        # as prefetch_related can be used if we do all() instead of filter()
        return [d for d in self.drawing_set.all() if d.is_public]

    def songs(self):
        return self._filter_on_language(self.song_set)

    def superbooks(self):
        return [d for d in self.superbook_set.all() if d.is_public]

    def henkieshows(self):
        cur_language = translation.get_language()
        # Since henkieshow is only available in the Dutch language, we only show this resource in Dutch
        if 'nl' in cur_language:
            return [d for d in self.henkieshow_set.all() if d.is_public]

    def short_movies(self):
        return self._filter_on_language(self.shortmovie_set)

    def pictures(self):
        return self.picture_set.filter(is_public=True)

    def testimonies(self):
        return self._filter_on_language(self.testimony_set)

    def questions(self):
        return self.question_set.all()

    def _filter_on_language(self, query):
        filter_languages = ['any'] + self.languages
        return query.filter(language__in=filter_languages, is_public=True)

    def _get_translated_bible_references(self, query_set):
        sorted_query_set = sorted(query_set)
        [ref.set_bible(self.bible) for ref in sorted_query_set]
        return sorted_query_set

    def __str__(self):
        return self.title
