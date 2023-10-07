import logging

from bible_lib import Bible, BibleBooks as BibleLibBibleBooks
from django.db import models
from django.utils.translation import gettext

from commandments_app.models import BibleBooks, Commandment, Lesson

class AbstractBibleReference(models.Model):
    """
    The abstract model of a bible reference.
    We store different types of bible references,
    but they share a lot of fields,
    the fields that are shared are in this model.
    """
    book = models.CharField(max_length=32,
                            choices=[(tag.name, tag.value) for tag in BibleBooks],
                            default=BibleBooks.Genesis,
                            help_text="The bible book like Genesis, Exodus, etc.")
    begin_chapter = models.IntegerField(default=1)
    begin_verse = models.IntegerField(default=1)
    end_chapter = models.IntegerField(default=0)
    end_verse = models.IntegerField(default=0)
    author = models.CharField(max_length=64, default='Undetermined')
    positive_negative = models.CharField(max_length=32,
                                         choices=[('positive', 'positive'),
                                                  ('negative', 'negative'),
                                                  ('both', 'both')],
                                         default='positive',
                                         help_text="Is this Bible text positive (encouraging), negative (discouraging) or both?")
    ot_nr = models.CharField(max_length=3, default='', null=True, blank=True)
    ot_rambam_id = models.CharField(max_length=32, default='', null=True, blank=True)
    ot_rambam_title = models.CharField(max_length=128, default='', null=True, blank=True)
    bible = None

    class Meta:
        abstract = True

    def set_bible(self, bible: Bible):
        """ Set a bible to get the text in that bible translation."""
        self.bible = bible

    def __str__(self):
        """ Get the bible verse formatted in the current language with the full book name like: Handelingen 1:1-2"""
        return f'{self.get_book_display()} {self._str_chapter_verses()}'

    def short_name(self):
        """ Get the bible verse with the untranslated abbreviation of the book, like: gen 1:1-2"""
        return f'{BibleLibBibleBooks.abbreviation(BibleLibBibleBooks[self.book])} {self._str_chapter_verses()}'

    def _str_chapter_verses(self):
        book_chapter_verse = f'{self.begin_chapter}:{self.begin_verse}'

        if self.begin_chapter == 0 or self.end_verse == 0:
            return book_chapter_verse

        if self.begin_chapter == self.end_chapter and self.begin_verse == self.end_verse:
            return book_chapter_verse

        if self.begin_chapter == self.end_chapter and self.end_verse > self.begin_verse:
            return f'{book_chapter_verse}-{self.end_verse}'

        return f'{book_chapter_verse}-{self.end_chapter}:{self.end_verse}'

    def text(self):
        """Get the verse text from the bible api."""
        if self.end_chapter == 0:
            end_chapter = self.begin_chapter
        else:
            end_chapter = self.end_chapter

        if self.end_verse == 0:
            end_verse = self.begin_verse
        else:
            end_verse = self.end_verse

        try:
            # Here we run into a bit of code smell, we do not use the enum provided by bible_lib,
            # As we want to translate the enum values. However before sending a query we convert to the bible_lib enum.
            return self.bible.verses(BibleLibBibleBooks[self.book],
                                     self.begin_chapter,
                                     self.begin_verse,
                                     end_chapter,
                                     end_verse)

        except Exception as ex:
            logging.getLogger().warning('Failed to load bible text')
            logging.getLogger().exception(ex)

        return gettext('Could not load text at the moment.')

    def __str__(self):
        book_chapter_verse = f'{self.get_book_display()} {self.begin_chapter}:{self.begin_verse}'

        if self.begin_chapter == 0 or self.end_verse == 0:
            return book_chapter_verse

        if self.begin_chapter == self.end_chapter and self.begin_verse == self.end_verse:
            return book_chapter_verse

        if self.begin_chapter == self.end_chapter and self.end_verse > self.begin_verse:
            return f'{book_chapter_verse}-{self.end_verse}'

        return f'{book_chapter_verse}-{self.end_chapter}:{self.end_verse}'

    def __lt__(self, other):
        if self.__class__ is not other.__class__:
            return NotImplemented

        if BibleBooks[self.book] < BibleBooks[other.book]:
            return True

        if BibleBooks[self.book] == BibleBooks[other.book] and self.begin_chapter < self.begin_chapter:
            return True

        if BibleBooks[self.book] == BibleBooks[other.book] and \
                self.begin_chapter == self.begin_chapter and \
                self.begin_verse < self.begin_verse:
            return True

        return False


class BibleReference(AbstractBibleReference):
    def __init__(self,
                 bible: Bible,
                 book: BibleBooks,
                 begin_chapter: int,
                 begin_verse: int,
                 end_chapter: int = 0,
                 end_verse: int = 0):
        self.bible = bible
        self.book = book.value
        self.begin_chapter = begin_chapter
        self.begin_verse = begin_verse
        self.end_chapter = end_chapter
        self.end_verse = end_verse

class PrimaryLessonBibleReference(AbstractBibleReference):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True, default=None, related_name='primary_lesson_bible_references')

    class Meta:
        unique_together = ['lesson', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']

class DirectLessonBibleReference(AbstractBibleReference):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True, default=None, related_name='direct_lesson_bible_references')

    class Meta:
        unique_together = ['lesson', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']

class PrimaryBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE, null=True, blank=True, default=None)


class DirectBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE, null=True, blank=True, default=None)

    class Meta:
        unique_together = ['commandment', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']


class IndirectBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['commandment', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']


class DuplicateBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['commandment', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']


class ExampleBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['commandment', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']


class StudyBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['commandment', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']


class OTLawBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['commandment', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse', 'ot_nr' ,'ot_rambam_id', 'ot_rambam_title']


class WisdomBibleReference(AbstractBibleReference):
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['commandment', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']
