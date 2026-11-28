from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from walkasjesus_app.lib.bible_numbering_checks import numbering_mapping_revision
from walkasjesus_app.lib.bible_numbering_review import check_needs_revalidation, numbering_review_status
from walkasjesus_app.models.bible_numbering import (
    BibleNumberingReview, BibleNumberingCheck, ensure_numbering_checklist,
    NUMBERING_CHECK_SCOPES,
)


class BibleNumberingCheckInline(admin.StackedInline):
    model = BibleNumberingCheck
    extra = 0
    can_delete = False
    readonly_fields = ('scope', 'reviewed_by', 'reviewed_at', 'review_validity')
    fields = (
        'scope', 'status', 'checked_passages', 'source', 'notes', 'follow_up',
        'reviewed_by', 'reviewed_at', 'review_validity',
    )

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description=_('Review validity'))
    def review_validity(self, obj):
        if check_needs_revalidation(obj):
            return _('The mapping or edition changed. Check the specified passages again.')
        return _('Confirmation applies only to the explicitly specified passages; it does not activate mappings.')


@admin.register(BibleNumberingReview)
class BibleNumberingReviewAdmin(admin.ModelAdmin):
    list_display = ('bible_id', 'edition', 'review_status', 'scanned_at')
    search_fields = ('bible_id', 'edition')
    inlines = (BibleNumberingCheckInline,)
    readonly_fields = ('review_status', 'scanned_at', 'report_summary')
    fields = ('bible_id', 'edition', 'notes', 'review_status', 'scanned_at', 'report_summary')

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, 'bible_id') if obj else fields

    @admin.display(description=_('Review status'))
    def review_status(self, obj):
        if obj is None or obj.pk is None:
            return _('Not checked')
        return numbering_review_status(obj)

    @admin.display(description=_('Latest cache-only report'))
    def report_summary(self, obj):
        if obj is None or not obj.report:
            return _('No scan yet. Run check_bible_numbering.sh; it makes no API requests.')
        lines = [
            str(_('This is a structural report, not proof of correct verse boundaries.')),
            str(_('Fresh cached references at scan time: %(count)s')) % {'count': obj.report.get('available_references', 0)},
            str(_('Cache entries: %(entries)s')) % {'entries': obj.report.get('entries', {})},
        ]
        if obj.mapping_revision != numbering_mapping_revision():
            lines.append(str(_('The mapping changed since this scan; run the cache-only checks again.')))
        for coverage in obj.report.get('chapter_catalogue_coverage', []):
            lines.append(str(_('Chapter coverage: %(book)s %(cached)s / %(expected)s')) % coverage)
        states = {
            'no_data': _('No fresh cache data'),
            'incomplete': _('Incomplete cache coverage'),
            'requires_manual_review': _('Manual comparison required'),
            'not_applicable': _('Not applicable to this edition'),
            'findings': _('Structural findings require review'),
            'no_structural_issues_detected': _('No structural issues detected in cached passages'),
            'no_merged_groups_observed': _('No merged ranges observed in cached passages'),
        }
        labels = dict(NUMBERING_CHECK_SCOPES)
        for scope, result in obj.report.get('scopes', {}).items():
            lines.append(f"{labels.get(scope, scope)}: {states.get(result['state'], result['state'])}")
            if 'expected_cases' in result:
                lines.append(str(_('Cached candidate references: %(cached)s / %(expected)s')) % {
                    'cached': result['cached_candidates'], 'expected': result['expected_cases'],
                })
                lines.append(str(_('Missing examples: %(references)s')) % {
                    'references': ', '.join(result['missing_examples']) or '—',
                })
            if 'group_count' in result:
                lines.append(str(_('Merged ranges: %(count)s')) % {'count': result['group_count']})
        findings = obj.report.get('findings', [])
        for finding in findings[:30]:
            lines.append(f"{finding['kind']}: {finding['reference']} - {finding['detail']}")
        if len(findings) > 30:
            lines.append(str(_('Additional findings: %(count)s (see JSON report).')) % {
                'count': len(findings) - 30,
            })
        return format_html('<pre style="white-space:pre-wrap">{}</pre>', '\n'.join(lines))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        ensure_numbering_checklist(obj)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            instance.reviewed_by = request.user
            instance.reviewed_at = timezone.now()
            instance.mapping_revision = numbering_mapping_revision()
            instance.reviewed_edition = form.instance.edition
            instance.save()
        formset.save_m2m()
