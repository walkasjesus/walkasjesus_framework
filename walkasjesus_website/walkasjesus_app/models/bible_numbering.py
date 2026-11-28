from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


NUMBERING_CHECK_SCOPES = (
    ('structure', _('Chapter and verse structure')),
    ('psalms', _('Psalm headings and verse boundaries')),
    ('hosea', _('Hosea chapter transitions')),
    ('joel', _('Joel chapter transitions')),
    ('merged', _('Merged and split verse blocks')),
)


class BibleNumberingReview(models.Model):
    bible_id = models.CharField(max_length=32, unique=True)
    edition = models.CharField(_('Edition / source version'), max_length=200, blank=True)
    notes = models.TextField(_('Dossier notes'), blank=True)
    report = models.JSONField(default=dict, blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    mapping_revision = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = _('Bible numbering review')
        verbose_name_plural = _('Bible numbering reviews')

    def __str__(self):
        return self.bible_id


class BibleNumberingCheck(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Not checked')
        REVIEWING = 'reviewing', _('Under investigation')
        CONFIRMED = 'confirmed', _('Confirmed for the specified passages')
        ISSUE = 'issue', _('Discrepancy found')
        UNCERTAIN = 'uncertain', _('Still uncertain')

    review = models.ForeignKey(BibleNumberingReview, on_delete=models.CASCADE, related_name='checks')
    scope = models.CharField(_('Check'), max_length=20, choices=NUMBERING_CHECK_SCOPES)
    status = models.CharField(_('Status'), max_length=12, choices=Status.choices, default=Status.PENDING)
    checked_passages = models.CharField(_('Checked passages / coverage'), max_length=500, blank=True)
    source = models.CharField(_('Reliable source (same edition)'), max_length=500, blank=True)
    notes = models.TextField(_('Evidence / explanation'), blank=True)
    follow_up = models.TextField(_('Next action'), blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    mapping_revision = models.CharField(max_length=64, blank=True)
    reviewed_edition = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = _('Numbering check')
        verbose_name_plural = _('Numbering checklist')
        constraints = [
            models.UniqueConstraint(fields=['review', 'scope'], name='unique_bible_numbering_scope'),
        ]

    def __str__(self):
        return str(self.get_scope_display())

    def clean(self):
        super().clean()
        if self.status == self.Status.CONFIRMED:
            errors = {}
            if not self.review.edition.strip():
                errors['__all__'] = _('Specify the edition in the dossier before confirming.')
            for field in ('checked_passages', 'source', 'notes'):
                if not str(getattr(self, field) or '').strip():
                    errors[field] = _('Specify the checked passages, source and evidence before confirming.')
            if errors:
                raise ValidationError(errors)
        if self.status == self.Status.ISSUE and not self.follow_up.strip():
            raise ValidationError({'follow_up': _('Describe the next action for this discrepancy.')})


def ensure_numbering_checklist(review):
    for scope, _label in NUMBERING_CHECK_SCOPES:
        review.checks.get_or_create(scope=scope)
