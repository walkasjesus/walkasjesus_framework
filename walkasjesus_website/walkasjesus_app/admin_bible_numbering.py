from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from walkasjesus_app.lib.bible_numbering_checks import numbering_mapping_revision
from walkasjesus_app.models.bible_numbering import (
    BibleNumberingReview,
    NUMBERING_CHECK_SCOPES,
)


@admin.register(BibleNumberingReview)
class BibleNumberingReviewAdmin(admin.ModelAdmin):
    list_display = ('bible_id', 'scanned_at')
    search_fields = ('bible_id',)
    readonly_fields = ('bible_id', 'scanned_at', 'report_summary')
    fields = readonly_fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_('Latest automatic report'))
    def report_summary(self, obj):
        if obj is None or not obj.report:
            return _('No scan yet. Run check_bible_numbering.sh.')
        lines = [
            str(_('This is a structural report, not proof of correct verse boundaries.')),
            str(_('Fresh cached references at scan time: %(count)s')) % {'count': obj.report.get('available_references', 0)},
            str(_('Cache entries: %(entries)s')) % {'entries': obj.report.get('entries', {})},
        ]
        acquisition = obj.report.get('acquisition', {})
        if acquisition:
            lines.append(str(_('API requests in this run: %(count)s')) % {'count': acquisition['requests']})
            if acquisition['budget_exhausted']:
                lines.append(str(_('Request budget reached; run the script again to continue.')))
            lines.extend(acquisition['errors'])
            lines.extend(acquisition['skipped'])
        if obj.mapping_revision != numbering_mapping_revision():
            lines.append(str(_('The mapping changed since this scan; run the cache-only checks again.')))
        for coverage in obj.report.get('chapter_catalogue_coverage', []):
            lines.append(str(_('Chapter coverage: %(book)s %(cached)s / %(expected)s')) % coverage)
        states = {
            'no_data': _('No fresh cache data'),
            'incomplete': _('Incomplete cache coverage'),
            'cached_candidates_available': _('Source references available; no automatic mapping approval'),
            'not_applicable': _('Not applicable to this edition'),
            'findings': _('Structural findings require review'),
            'no_structural_issues_detected': _('No structural issues detected in cached passages'),
            'no_merged_groups_observed': _('No merged ranges observed in cached passages'),
            'no_known_numbering_differences': _('No numbering differences in the local reference mapping'),
            'no_reference_mapping': _('No local numbering reference mapping available'),
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
