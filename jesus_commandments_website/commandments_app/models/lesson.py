from django.db import models
from django.utils import translation

from commandments_app.models import LessonCategories

class LessonManager(models.Manager):
    def with_background(self):
        return (c for c in Lesson.objects.all().prefetch_related('lessondrawing_set') if c.background_drawing())

class Lesson(models.Model):
    title = models.CharField(max_length=256, help_text="The title of the lesson")
    category = models.CharField(max_length=64,
                                choices=[(tag.name, tag.value) for tag in LessonCategories],
                                default=LessonCategories.oldtestament)
    bible_section = models.CharField(max_length=128, default='', blank=True, help_text="The bible books which covers the lesson")
    bible = None
    languages = [translation.get_language()]
    objects = LessonManager()
    def primary_bible_reference(self):
        reference = self.primary_lesson_bible_references.first()
        if reference:
            reference.set_bible(self.bible)
        return reference

    def direct_bible_references(self):
        return self._get_translated_bible_references(self.direct_lesson_bible_references.all())

    def background_drawing(self):
        return self.drawings()[0] if self.drawings() else ''

    def background_song(self):
        return self.songs()[0] if self.songs() else ''

    def found_superbook(self):
        return self.superbooks()[0] if self.superbooks() else ''

    def found_henkieshow(self):
        return self.henkieshows()[0] if self.henkieshows() else ''

    def drawings(self):
        return [d for d in self.lessondrawing_set.all() if d.is_public]

    def songs(self):
        return self._filter_on_language(self.lessonsong_set)

    def superbooks(self):
        return [d for d in self.lessonsuperbook_set.all() if d.is_public]

    def henkieshows(self):
        cur_language = translation.get_language()
        if 'nl' in cur_language:
            return [d for d in self.lessonhenkieshow_set.all() if d.is_public]

    def short_movies(self):
        return self._filter_on_language(self.lessonshortmovie_set)

    def pictures(self):
        return self.lessonpicture_set.filter(is_public=True)

    def testimonies(self):
        return self._filter_on_language(self.lessontestimony_set)

    def questions(self):
        return self.lessonquestion_set.all()

    def _filter_on_language(self, query):
        filter_languages = ['any'] + self.languages
        return query.filter(language__in=filter_languages, is_public=True)

    def _get_translated_bible_references(self, query_set):
        sorted_query_set = sorted(query_set)
        [ref.set_bible(self.bible) for ref in sorted_query_set]
        return sorted_query_set

    def __str__(self):
        return self.title
