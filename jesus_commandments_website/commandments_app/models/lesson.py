from django.db import models
from django.utils import translation
from ckeditor.fields import RichTextField

from commandments_app.models import Commandment, LessonCategories

class LessonManager(models.Manager):
    def with_background(self):
        return (c for c in Lesson.objects.all().prefetch_related('lessondrawing_set') if c.background_drawing())

class Lesson(models.Model):
    title = models.CharField(max_length=256, help_text="The step of the lesson which will be learned")
    story = models.CharField(max_length=256, help_text="The title of the lesson from the Childrens Bible", null=True, blank=True, default=None)
    activities = RichTextField(help_text="Beschrijf bij de les horende actititeiten, verwerkingsopdrachten of een leuke sketch. Wees creatief!", null=True, blank=True, default=None)
    category = models.CharField(max_length=64,
                                choices=[(tag.name, tag.value) for tag in LessonCategories],
                                default=LessonCategories.oldtestament)
    commandment = models.ForeignKey(Commandment, help_text="If there is a connection to a commandment/step with this lesson, connect it here", on_delete=models.CASCADE, null=True, blank=True, default=None)
    related_step_description = models.CharField(max_length=512, help_text="A description why this step is related to the Lesson from the Childrens Bible", null=True, blank=True, default=None)
    bible = None
    languages = [translation.get_language()]
    objects = LessonManager()

    def bible_section(self):
        """
        The rough Bible section of the lesson from the Childrens Bible which this lesson is mainly about
        """
        return self._get_translated_bible_references(self.lesson_bible_section.all())

    def primary_bible_reference(self, include_commandment_reference=True):
        lesson_reference = self.primary_lesson_bible_references.first()
        if lesson_reference:
            lesson_reference.set_bible(self.bible)
       
        if include_commandment_reference and self.commandment:
            self.commandment.bible = self.bible
            return self.commandment.primary_bible_reference()
        else:
            return lesson_reference

    def direct_bible_references(self, include_commandment_reference=True):
        lesson_references = self._get_translated_bible_references(self.direct_lesson_bible_references.all())

        if include_commandment_reference and self.commandment:
            commandment_references = self.commandment.direct_bible_references()
        else:
            commandment_references = []

        return lesson_references + commandment_references

    def background_drawing(self):
        return self.drawings()[0] if self.drawings() else ''

    def background_song(self):
        return self.songs()[0] if self.songs() else ''

    def found_superbook(self):
        return self.superbooks()[0] if self.superbooks() else ''

    def found_henkieshow(self):
        return self.henkieshows()[0] if self.henkieshows() else ''

    def drawings(self):
        lesson_drawings = [d for d in self.lessondrawing_set.all() if d.is_public]

        if self.commandment:
            commandment_drawings = []
            commandment_drawings = self.commandment.drawings()
            return list(lesson_drawings) + list(commandment_drawings)
        else:
            return list(lesson_drawings)


    def songs(self):
        lesson_songs = self._filter_on_language(self.lessonsong_set)

        if self.commandment:
            commandment_songs = self.commandment.songs().filter(target_audience__in=['any', 'kids'])
            return list(lesson_songs) + list(commandment_songs)
        else:
            return list(lesson_songs)


    def superbooks(self):
        """We only want to display the superbooks of the lesson, since the superbooks of the commandment are chosen based on subject, while the lesson has more focus on the Bible story"""
        return [d for d in self.lessonsuperbook_set.all() if d.is_public]

    def henkieshows(self, include_commandment_media=True):
        cur_language = translation.get_language()
        if 'nl' in cur_language:
            lesson_media = [d for d in self.lessonhenkieshow_set.all() if d.is_public]

            if include_commandment_media and self.commandment:
                return lesson_media + self.commandment.henkieshows()
            else:
                return lesson_media

    def short_movies(self):
        lesson_short_movies = self._filter_on_language(self.lessonshortmovie_set)

        if self.commandment:
            commandment_short_movies = []
            commandment_short_movies = self.commandment.short_movies().filter(target_audience__in=['any', 'kids'])
            return list(lesson_short_movies) + list(commandment_short_movies)
        else:
            return list(lesson_short_movies)


    def pictures(self):
        lesson_pictures = self.lessonpicture_set.filter(is_public=True)

        if self.commandment:
            commandment_pictures = []
            commandment_pictures = self.commandment.pictures().filter(target_audience__in=['any', 'kids'])
            return list(lesson_pictures) + list(commandment_pictures)
        else:
            return list(lesson_pictures)

    def testimonies(self):
        lesson_testimonies = self._filter_on_language(self.lessontestimony_set)

        if self.commandment:
            commandment_testimonies = []
            commandment_testimonies = self.commandment.testimonies().filter(target_audience__in=['any', 'kids'])
            return list(lesson_testimonies) + list(commandment_testimonies)
        else:
            return list(lesson_testimonies)

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