from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy
import hashlib

import requests

from .bible_books import BibleBooks


def _ncla_choices():
    person_labels = {
        'JM': 'Jewish male',
        'JF': 'Jewish female',
        'KM': "K'rov Yisrael male",
        'KF': "K'rovat Yisrael female",
        'GM': 'Gentile male',
        'GF': 'Gentile female',
    }
    application_labels = {
        'm': 'mandated',
        'r': 'recommended',
        'o': 'optional',
        'n': 'not generally recommended',
        'u': 'unauthorized',
        'p': 'prohibited',
        'i': 'impossible',
    }

    choices = []
    for person_code, person_label in person_labels.items():
        for application_code, application_label in application_labels.items():
            code = f'{person_code}{application_code}'
            choices.append((code, f'{code} - {person_label}, {application_label}'))

    return choices


COMMENTARY_TRANSLATION_CACHE_TIMEOUT = int(getattr(settings, 'COMMENTARY_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))


def _split_translation_chunks(text, max_len=4200):
    chunks = []
    for paragraph in str(text or '').split('\n\n'):
        part = paragraph.strip()
        if not part:
            continue
        if len(part) <= max_len:
            chunks.append(part)
            continue

        for i in range(0, len(part), max_len):
            chunks.append(part[i:i + max_len])
    return chunks


def _translate_en_to_language(text, target_language):
    chunks = _split_translation_chunks(text)
    translated_chunks = []

    for chunk in chunks:
        response = requests.get(
            'https://translate.googleapis.com/translate_a/single',
            params={
                'client': 'gtx',
                'sl': 'en',
                'tl': target_language,
                'dt': 't',
                'q': chunk,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        segments = data[0] if isinstance(data, list) and data else []
        translated_parts = [segment[0] for segment in segments if isinstance(segment, list) and segment and segment[0]]
        translated_chunks.append(''.join(translated_parts))

    return '\n\n'.join(translated_chunks)


def _translated_dynamic_commentary(text):
    source_text = str(text or '').strip()
    if not source_text:
        return ''

    translated_text = _(source_text)
    language = (get_language() or 'en').lower()[:2]

    # If a PO translation exists (or UI language is English), prefer that path.
    if language == 'en' or translated_text != source_text:
        return translated_text

    digest = hashlib.sha256(f'{language}:{source_text}'.encode('utf-8')).hexdigest()
    cache_key = f'law_of_messiah_commentary_translation:v1:{digest}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        machine_translated = _translate_en_to_language(source_text, language)
        if machine_translated:
            cache.set(cache_key, machine_translated, COMMENTARY_TRANSLATION_CACHE_TIMEOUT)
            return machine_translated
    except Exception:
        pass

    return translated_text


class LawOfMessiah(models.Model):
    HUMAN_READABLE_NAME_EN = 'Law of Messiah'
    HUMAN_READABLE_NAME_NL = 'Wet van de Messias'

    SOURCE_DATASET_OT = 'ot'
    SOURCE_DATASET_NT = 'nt'
    SOURCE_DATASET_CHOICES = [
        (SOURCE_DATASET_OT, 'Old Testament'),
        (SOURCE_DATASET_NT, 'New Testament'),
    ]

    COMMANDMENT_TYPE_POSITIVE = 'positive'
    COMMANDMENT_TYPE_NEGATIVE = 'negative'
    COMMANDMENT_TYPE_BOTH = 'both'
    COMMANDMENT_TYPE_CHOICES = [
        (COMMANDMENT_TYPE_POSITIVE, 'Positive'),
        (COMMANDMENT_TYPE_NEGATIVE, 'Negative'),
        (COMMANDMENT_TYPE_BOTH, 'Positive & Negative'),
    ]

    COMMANDMENT_FORM_EXPLICIT = 'explicit'
    COMMANDMENT_FORM_IMPLIED = 'implied'
    COMMANDMENT_FORM_EMPTY = ''
    COMMANDMENT_FORM_CHOICES = [
        (COMMANDMENT_FORM_EMPTY, '-'),
        (COMMANDMENT_FORM_EXPLICIT, 'Explicit'),
        (COMMANDMENT_FORM_IMPLIED, 'Implied'),
    ]

    NCLA_CHOICES = _ncla_choices()

    id = models.CharField(max_length=32, primary_key=True)
    source_dataset = models.CharField(max_length=16, choices=SOURCE_DATASET_CHOICES, default=SOURCE_DATASET_OT)

    title = models.CharField(max_length=512, blank=True, default='')
    commandment = models.TextField(blank=True, default='')
    commandment_subtitles = models.JSONField(default=list, blank=True)
    commandment_type = models.CharField(max_length=64, choices=COMMANDMENT_TYPE_CHOICES, default=COMMANDMENT_TYPE_POSITIVE)
    commandment_form = models.CharField(max_length=64, choices=COMMANDMENT_FORM_CHOICES, default=COMMANDMENT_FORM_EMPTY, blank=True)
    category = models.CharField(max_length=256, blank=True, default='')
    is_unique = models.BooleanField(default=False)
    double_ids = models.JSONField(default=list, blank=True)

    commentary_rudolph = models.TextField(blank=True, default='')
    commentary_juster = models.TextField(blank=True, default='')
    classical_commentators = models.TextField(blank=True, default='')

    commandments_related_ot = models.JSONField(default=list, blank=True)
    commandments_related_nt = models.JSONField(default=list, blank=True)
    related_lawofmessiah = models.JSONField(default=list, blank=True)
    related_steps = models.ManyToManyField('Commandment', blank=True, related_name='law_of_messiah_related_steps')
    maimonides = models.JSONField(default=list, blank=True)
    meir = models.JSONField(default=list, blank=True)
    chinuch = models.JSONField(default=list, blank=True)

    ncla = models.JSONField(default=list, blank=True)
    ncla_deviation = models.BooleanField(default=False)
    classical_commandment = models.BooleanField(default=False)

    source = models.TextField(blank=True, default='')
    copyright = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Law of Messiah'
        verbose_name_plural = 'Law of Messiah'
        ordering = ['id']

    @property
    def subtitle_texts(self):
        import ast
        texts = []
        for item in self.commandment_subtitles:
            if isinstance(item, dict):
                texts.append(item.get('commandment', str(item)))
            elif isinstance(item, str):
                try:
                    parsed = ast.literal_eval(item)
                    if isinstance(parsed, dict):
                        texts.append(parsed.get('commandment', item))
                    else:
                        texts.append(item)
                except Exception:
                    texts.append(item)
            else:
                texts.append(str(item))
        return texts

    @classmethod
    def human_readable_name(cls, language='en'):
        return cls.HUMAN_READABLE_NAME_NL if language.lower().startswith('nl') else cls.HUMAN_READABLE_NAME_EN

    @property
    def translated_title(self):
        return _(self.title) if self.title else self.id

    @property
    def translated_commandment(self):
        return _(self.commandment) if self.commandment else ''

    @property
    def translated_category(self):
        return _(self.category) if self.category else '-'

    @property
    def translated_commandment_type_display(self):
        return _(self.get_commandment_type_display())

    @property
    def translated_commandment_form_display(self):
        value = self.get_commandment_form_display()
        return _(value) if value else '-'

    @property
    def translated_source_dataset_display(self):
        return _(self.get_source_dataset_display())

    @property
    def translated_commentary_rudolph(self):
        return _translated_dynamic_commentary(self.commentary_rudolph)

    @property
    def translated_commentary_juster(self):
        return _translated_dynamic_commentary(self.commentary_juster)

    @property
    def translated_classical_commentators(self):
        return _translated_dynamic_commentary(self.classical_commentators)

    def __str__(self):
        if self.title:
            return f'{self.id} - {self.title}'
        return self.id

    def key_nt_scriptures(self):
        return self.bible_reference_rows.filter(reference_type=LawOfMessiahBibleReference.TYPE_KEY_NT)

    def key_ot_scriptures(self):
        return self.bible_reference_rows.filter(reference_type=LawOfMessiahBibleReference.TYPE_KEY_OT)

    def supportive_nt_scriptures(self):
        return self.bible_reference_rows.filter(reference_type=LawOfMessiahBibleReference.TYPE_SUPPORTIVE_NT)

    def supportive_ot_scriptures(self):
        return self.bible_reference_rows.filter(reference_type=LawOfMessiahBibleReference.TYPE_SUPPORTIVE_OT)


class LawOfMessiahBibleReference(models.Model):
    TYPE_KEY_NT = 'key_nt_scriptures'
    TYPE_KEY_OT = 'key_ot_scriptures'
    TYPE_SUPPORTIVE_NT = 'supportive_nt_scriptures'
    TYPE_SUPPORTIVE_OT = 'supportive_ot_scriptures'
    TYPE_CHOICES = [
        (TYPE_KEY_NT, 'Key NT Scriptures'),
        (TYPE_KEY_OT, 'Key OT Scriptures'),
        (TYPE_SUPPORTIVE_NT, 'Supportive NT Scriptures'),
        (TYPE_SUPPORTIVE_OT, 'Supportive OT Scriptures'),
    ]

    law_of_messiah = models.ForeignKey(LawOfMessiah, on_delete=models.CASCADE, related_name='bible_reference_rows')
    reference_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
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
        ordering = ['reference_type', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse', 'id']

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

    def scriptura_book(self):
        from django.utils import translation
        with translation.override('en'):
            return f'{self.get_book_display()}'

    def scriptura_chapter(self):
        return self.begin_chapter

    def scriptura_verse(self):
        return self.begin_verse

    def verse_count_estimate(self):
        if self.begin_chapter == 0 or self.end_verse == 0:
            return 1

        end_chapter = self.end_chapter or self.begin_chapter
        end_verse = self.end_verse or self.begin_verse

        if end_chapter == self.begin_chapter:
            return max(1, (end_verse - self.begin_verse) + 1)

        # For cross-chapter ranges, we intentionally treat it as long.
        return 999

    def is_long_passage(self):
        threshold = max(1, int(getattr(settings, 'BIBLE_AUTO_LOAD_VERSE_LIMIT', 5)))
        return self.verse_count_estimate() > threshold

    def is_ot(self):
        """Returns True if this is an Old Testament reference, False for New Testament."""
        return 'ot' in self.reference_type

    def __str__(self):
        return f"{self.get_reference_type_display()}: {self.display_reference()}"
