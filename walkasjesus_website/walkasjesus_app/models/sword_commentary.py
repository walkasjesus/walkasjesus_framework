from django.db import models


class SwordCommentarySource(models.Model):
    source_id = models.CharField(max_length=64, unique=True)
    module_name = models.CharField(max_length=128, default='')
    display_name = models.CharField(max_length=128, default='')
    language = models.CharField(max_length=8, default='en')
    copyright_text = models.TextField(default='', blank=True)
    source_path = models.CharField(max_length=512, default='')
    sort_order = models.IntegerField(default=100)
    is_enabled = models.BooleanField(default=True)
    last_imported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['sort_order', 'display_name', 'source_id']

    def __str__(self):
        return f'{self.source_id} ({self.language})'


class SwordCommentaryEntry(models.Model):
    source = models.ForeignKey(SwordCommentarySource, on_delete=models.CASCADE, related_name='entries')
    book = models.CharField(max_length=32)
    book_key = models.CharField(max_length=32, db_index=True)
    chapter = models.PositiveIntegerField()
    verse = models.PositiveIntegerField()
    text = models.TextField(default='', blank=True)

    class Meta:
        ordering = ['source_id', 'book', 'chapter', 'verse']
        indexes = [
            models.Index(fields=['source', 'book_key', 'chapter']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['source', 'book_key', 'chapter', 'verse'], name='uniq_sword_source_book_chapter_verse'),
        ]

    def __str__(self):
        return f'{self.source.source_id} {self.book} {self.chapter}:{self.verse}'