from django.db import models
from django.utils import translation

from commandments_app.models import Commandment, LessonCategories

class LessonManager(models.Manager):
    def with_background(self):
        return (c for c in Lesson.objects.all().prefetch_related('lessondrawing_set') if c.background_drawing())

class Lesson(models.Model):
    title = models.CharField(max_length=256, help_text="The title of the lesson")
    category = models.CharField(max_length=64,
                                choices=[(tag.name, tag.value) for tag in LessonCategories],
                                default=LessonCategories.oldtestament)
    bible_section = models.CharField(max_length=128, default='', blank=True, help_text="The bible books which covers the lesson")
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE, null=True, blank=True, default=None)
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

    def drawings(self, include_commandment_media=True):
        lesson_media = [d for d in self.lessondrawing_set.all() if d.is_public]

        if include_commandment_media and self.commandment:
            return lesson_media + self.commandment.drawings()
        else:
            return lesson_media

    def songs(self, include_commandment_media=True):
        lesson_media = self._filter_on_language(self.lessonsong_set)

        if include_commandment_media and self.commandment:
            return list(lesson_media) + list(self.commandment.songs())
        else:
            return list(lesson_media)

    def superbooks(self, include_commandment_media=True):
        lesson_media = [d for d in self.lessonsuperbook_set.all() if d.is_public]

        if include_commandment_media and self.commandment:
            return lesson_media + self.commandment.superbooks()
        else:
            return lesson_media

    def henkieshows(self, include_commandment_media=True):
        cur_language = translation.get_language()
        if 'nl' in cur_language:
            lesson_media = [d for d in self.lessonhenkieshow_set.all() if d.is_public]

            if include_commandment_media and self.commandment:
                return lesson_media + self.commandment.henkieshows()
            else:
                return lesson_media

    def short_movies(self, include_commandment_media=True):
        lesson_media = self._filter_on_language(self.lessonshortmovie_set)

        if include_commandment_media and self.commandment:
            return list(lesson_media) + list(self.commandment.short_movies())
        else:
            return list(lesson_media)

    def pictures(self, include_commandment_media=True):
        lesson_media = self.lessonpicture_set.filter(is_public=True)

        if include_commandment_media and self.commandment:
            return list(lesson_media) + list(self.commandment.pictures())
        else:
            return list(lesson_media)

    def testimonies(self, include_commandment_media=True):
        lesson_media = self._filter_on_language(self.lessontestimony_set)

        if include_commandment_media and self.commandment:
            return list(lesson_media) + list(self.commandment.testimonies())
        else:
            return list(lesson_media)

    def lessonquestions(self):
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