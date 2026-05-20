from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy

from .bible_books import BibleBooks


class Maimonides(models.Model):
    """Maimonides' 613 commandments - historical Jewish interpretation of Torah mitzvot."""

    COMMANDMENT_TYPE_POSITIVE = 'positive'
    COMMANDMENT_TYPE_NEGATIVE = 'negative'
    COMMANDMENT_TYPE_CHOICES = [
        (COMMANDMENT_TYPE_POSITIVE, 'Positive'),
        (COMMANDMENT_TYPE_NEGATIVE, 'Negative'),
    ]

    id = models.CharField(max_length=16, primary_key=True)
    commandment_type = models.CharField(max_length=32, choices=COMMANDMENT_TYPE_CHOICES, default=COMMANDMENT_TYPE_POSITIVE)
    commandment = models.TextField(blank=True, default='')
    meir = models.JSONField(default=list, blank=True)
    chinuch = models.JSONField(default=list, blank=True)
    rudolph = models.JSONField(default=list, blank=True)
    scriptures = models.JSONField(default=list, blank=True)
    meir_scriptures = models.JSONField(default=list, blank=True)
    chinuch_scriptures = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'Maimonides commandment'
        verbose_name_plural = 'Maimonides Commandments'
        ordering = ['id']

    def maimonides_scriptures(self):
        return self.bible_reference_rows.filter(reference_type=MaimonidesBibleReference.TYPE_MAIMONIDES)

    def meir_scriptures_rows(self):
        return self.bible_reference_rows.filter(reference_type=MaimonidesBibleReference.TYPE_MEIR)

    def chinuch_scriptures_rows(self):
        return self.bible_reference_rows.filter(reference_type=MaimonidesBibleReference.TYPE_CHINUCH)

    def __str__(self):
        return f'{self.id} - {self.commandment}'


class MaimonidesBibleReference(models.Model):
    TYPE_MAIMONIDES = 'maimonides_scriptures'
    TYPE_MEIR = 'meir_scriptures'
    TYPE_CHINUCH = 'chinuch_scriptures'
    TYPE_CHOICES = [
        (TYPE_MAIMONIDES, 'Maimonides Scriptures'),
        (TYPE_MEIR, 'Meir Scriptures'),
        (TYPE_CHINUCH, 'HaChinuch Scriptures'),
    ]

    maimonides = models.ForeignKey(Maimonides, on_delete=models.CASCADE, related_name='bible_reference_rows')
    reference_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    source_code = models.CharField(max_length=32, blank=True, default='')
    book = models.CharField(
        max_length=32,
        choices=[(tag.name, tag.value) for tag in BibleBooks],
        default=BibleBooks.Genesis,
        help_text=gettext_lazy('The bible book like Genesis, Exodus, etc.'),
    )
    begin_chapter = models.IntegerField(default=0)
    begin_verse = models.IntegerField(default=0)
    end_chapter = models.IntegerField(default=0)
    end_verse = models.IntegerField(default=0)

    class Meta:
        ordering = ['reference_type', 'source_code', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse', 'id']

    def _str_chapter_verses(self):
        start = f'{self.begin_chapter}:{self.begin_verse}'

        if self.begin_chapter == 0 or self.end_verse == 0:
            return start

        if self.begin_chapter == self.end_chapter and self.begin_verse == self.end_verse:
            return start

        if self.begin_chapter == self.end_chapter and self.end_verse > self.begin_verse:
            return f'{start}-{self.end_verse}'

        return f'{start}-{self.end_chapter}:{self.end_verse}'

    def display_reference(self):
        return f'{self.get_book_display()} {self._str_chapter_verses()}'

    def sefaria_reference(self):
        from django.utils import translation
        with translation.override('en'):
            return f'{self.get_book_display()} {self._str_chapter_verses()}'

    def client_ref_id(self):
        return f'{self.__class__.__name__}:{self.pk}'

    def verse_count_estimate(self):
        if self.begin_chapter == 0 or self.end_verse == 0:
            return 1

        end_chapter = self.end_chapter or self.begin_chapter
        end_verse = self.end_verse or self.begin_verse
        if end_chapter == self.begin_chapter:
            return max(1, (end_verse - self.begin_verse) + 1)
        return 999

    def is_long_passage(self):
        threshold = max(1, int(getattr(settings, 'BIBLE_AUTO_LOAD_VERSE_LIMIT', 5)))
        return self.verse_count_estimate() > threshold

    def scriptura_book(self):
        from django.utils import translation
        with translation.override('en'):
            return f'{self.get_book_display()}'

    def scriptura_chapter(self):
        return self.begin_chapter

    def scriptura_verse(self):
        return self.begin_verse

    def is_ot(self):
        return BibleBooks[self.book] <= BibleBooks.Malachi

    def __str__(self):
        prefix = f'{self.source_code}: ' if self.source_code else ''
        return f'{prefix}{self.display_reference()}'
