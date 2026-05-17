from django.db import models
from django.utils import translation

from walkasjesus_app.media_image_utils import media_file_exists
from walkasjesus_app.models.commandment_categories import CommandmentCategories


class CommandmentManager(models.Manager):
    def with_background(self):
        """
        Allow to use Commandment.objects.with_background(),
        this is the same as Commandment.objects.all(),
        but it preloads the drawings therefor reducing the number of queries
        (at least it reduces queries if we do need the drawings)
        """
        return (c for c in Commandment.objects.all().prefetch_related('drawing_set') if c.background_drawing())


class Commandment(models.Model):
    title = models.CharField(max_length=256)
    title_negative = models.CharField(max_length=256, default='', blank=True)
    category = models.CharField(max_length=256, default='', blank=True)
    quote = models.TextField(default='', blank=True, null=True)
    quote_source = models.CharField(max_length=256, default='', blank=True, null=True)
    bible = None
    languages = [translation.get_language()]
    objects = CommandmentManager()

    def get_category_display(self):
        try:
            return CommandmentCategories[self.category].value
        except KeyError:
            try:
                return CommandmentCategories(self.category).value
            except ValueError:
                return self.category

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

    def indirect_bible_references(self):
        """ Extra, more indirect Bible references, relating to the same commandment. """
        return self._get_translated_bible_references(self.indirectbiblereference_set.all())

    def duplicate_bible_references(self):
        """ Another Bible reference to more or less the same as the primary, direct or indirect, 
        with not much new information, although it will confirm the same Bible references. """
        return self._get_translated_bible_references(self.duplicatebiblereference_set.all())

    def example_bible_references(self):
        """ In these Bible references you will find examples and testimonies how this commandment  
        is being executed. """
        return self._get_translated_bible_references(self.examplebiblereference_set.all())

    def study_bible_references(self):
        """ Extra Bible references (most often larger parts of Bible books) which are good for 
        extra study on this commandment. """
        return self._get_translated_bible_references(self.studybiblereference_set.all())

    def otlaw_bible_references(self):
        """ Old Testament Law Bible references which will relate to OT Commandments (Jewish 
        tradition teached that there are 613 commandments or mitzvot in the Torah) """
        return self._get_translated_bible_references(self.otlawbiblereference_set.all())

    def wisdom_bible_references(self):
        """ Wisdom Bible references will relate to one of the Wisdom Literare Books from the 
        Old Testament """
        return self._get_translated_bible_references(self.wisdombiblereference_set.all())

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
        legacy = [d for d in self.drawing_set.all() if d.is_public and media_file_exists(d.img_url)]
        if legacy:
            return legacy
        shared = [d for d in self.shared_media_resources.filter(media_type='drawing', is_public=True) if media_file_exists(d.img_url)]
        if shared:
            return shared
        legacy_fallback = [d for d in self.drawing_set.all() if d.is_public]
        if legacy_fallback:
            return legacy_fallback
        return list(self.shared_media_resources.filter(media_type='drawing', is_public=True))

    def songs(self):
        return self._filter_on_language(self.song_set)

    def superbooks(self):
        return [d for d in self.superbook_set.all() if d.is_public]

    def henkieshows(self):
        cur_language = translation.get_language()
        # Since henkieshow is only available in the Dutch language, we only show this resource in Dutch
        if 'nl' in cur_language:
            return [d for d in self.henkieshow_set.all() if d.is_public]

    def movies(self):
        return self._filter_on_language(self.movie_set)

    def short_movies(self):
        return self._filter_on_language(self.shortmovie_set)

    def waj_video(self):
        return self._filter_on_language(self.wajvideo_set)

    def sermons(self):
        return self._filter_on_language(self.sermon_set)

    def pictures(self):
        return self.picture_set.filter(is_public=True)

    def testimonies(self):
        return self._filter_on_language(self.testimony_set)

    def blogs(self):
        return self._filter_on_language(self.blog_set)

    def books(self):
        return self._filter_on_language(self.book_set)

    def questions(self):
        return self.question_set.all()

    def _filter_on_language(self, query):
        filter_languages = ['any'] + self.languages
        return query.filter(language__in=filter_languages, is_public=True)

    def _get_translated_bible_references(self, query_set):
        sorted_query_set = sorted(query_set)
        [ref.set_bible(self.bible) for ref in sorted_query_set]
        return sorted_query_set

    class Meta:
        verbose_name = 'Step'
        verbose_name_plural = 'Steps'
        ordering = ['id']

    def __str__(self):
        if self.title:
            return f'{self.id} - {self.title}'
        return str(self.id)
