from django.db import models


class BibleTranslationUsageDaily(models.Model):
    SOURCE_API = 'api'
    SOURCE_CACHE = 'cache'
    SOURCE_CHOICES = (
        (SOURCE_API, 'API'),
        (SOURCE_CACHE, 'Cache'),
    )

    ENDPOINT_STUDY_PAGE = 'study_page'
    ENDPOINT_VERSES_API = 'verses_api'
    ENDPOINT_CHOICES = (
        (ENDPOINT_STUDY_PAGE, 'Bible Study page'),
        (ENDPOINT_VERSES_API, 'Bible Study verses API'),
    )

    USER_AUTHENTICATED = 'authenticated'
    USER_ANONYMOUS = 'anonymous'
    USER_KIND_CHOICES = (
        (USER_AUTHENTICATED, 'Authenticated'),
        (USER_ANONYMOUS, 'Anonymous'),
    )

    usage_date = models.DateField(db_index=True)
    bible_id = models.CharField(max_length=64, db_index=True)
    bible_name = models.CharField(max_length=255, blank=True, default='')
    bible_language = models.CharField(max_length=8, blank=True, default='')
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, db_index=True)
    endpoint = models.CharField(max_length=32, choices=ENDPOINT_CHOICES, db_index=True)
    user_kind = models.CharField(max_length=16, choices=USER_KIND_CHOICES, db_index=True)
    user_key = models.CharField(max_length=64, db_index=True)
    request_count = models.PositiveIntegerField(default=0)
    verse_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['usage_date', 'bible_id', 'source', 'endpoint', 'user_key'],
                name='uniq_bible_usage_daily_bucket',
            ),
        ]
        indexes = [
            models.Index(fields=['usage_date', 'bible_id']),
            models.Index(fields=['usage_date', 'source']),
            models.Index(fields=['bible_id', 'user_key']),
        ]
        ordering = ['-usage_date', 'bible_id', 'source', 'endpoint']
        verbose_name = 'Bible usage report'
        verbose_name_plural = 'Bible Usage Report'

    def __str__(self):
        return f'{self.usage_date} {self.bible_id} {self.source} {self.user_kind} {self.user_key}'


class PageVisitDaily(models.Model):
    USER_AUTHENTICATED = 'authenticated'
    USER_ANONYMOUS = 'anonymous'
    USER_KIND_CHOICES = (
        (USER_AUTHENTICATED, 'Authenticated'),
        (USER_ANONYMOUS, 'Anonymous'),
    )

    usage_date = models.DateField(db_index=True)
    page_path = models.CharField(max_length=512, db_index=True)
    page_label = models.CharField(max_length=255, blank=True, default='')
    language_code = models.CharField(max_length=8, blank=True, default='')
    user_kind = models.CharField(max_length=16, choices=USER_KIND_CHOICES, db_index=True)
    user_key = models.CharField(max_length=64, db_index=True)
    visit_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['usage_date', 'page_path', 'language_code', 'user_key'],
                name='uniq_page_visit_daily_bucket',
            ),
        ]
        indexes = [
            models.Index(fields=['usage_date', 'page_path']),
            models.Index(fields=['usage_date', 'language_code']),
            models.Index(fields=['page_path', 'user_key']),
        ]
        ordering = ['-usage_date', 'page_path', 'language_code']
        verbose_name = 'Page usage report'
        verbose_name_plural = 'Page Usage Report'

    def __str__(self):
        return f'{self.usage_date} {self.page_path} {self.language_code} {self.user_kind} {self.user_key}'
