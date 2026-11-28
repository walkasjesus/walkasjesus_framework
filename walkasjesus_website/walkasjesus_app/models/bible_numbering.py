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
    legacy_checks = models.JSONField(default=list, blank=True, editable=False)

    class Meta:
        verbose_name = _('Bible numbering report')
        verbose_name_plural = _('Bible numbering reports')

    def __str__(self):
        return self.bible_id
