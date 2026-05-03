from django.db import models
from django.utils.translation import gettext_lazy

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


class LawOfMessiah(models.Model):
    HUMAN_READABLE_NAME_EN = 'Law of Messiah'
    HUMAN_READABLE_NAME_NL = 'Wet van Christus'

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
        return self.verse_count_estimate() > 5

    def __str__(self):
        return f"{self.get_reference_type_display()}: {self.display_reference()}"
