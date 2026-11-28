from django.utils.translation import gettext as _

from walkasjesus_app.lib.bible_numbering_checks import numbering_mapping_revision
from walkasjesus_app.models.bible_numbering import BibleNumberingCheck


def check_needs_revalidation(check):
    return check.status == BibleNumberingCheck.Status.CONFIRMED and (
        not check.review.edition.strip()
        or check.mapping_revision != numbering_mapping_revision()
        or check.reviewed_edition != check.review.edition
    )


def numbering_review_status(review):
    checks = list(review.checks.all())
    if any(check.status == BibleNumberingCheck.Status.ISSUE for check in checks):
        return _('Discrepancy found')
    if any(check_needs_revalidation(check) for check in checks):
        return _('Review needs updating')
    if any(check.status == BibleNumberingCheck.Status.CONFIRMED for check in checks):
        return _('Partially reviewed; only the specified passages')
    if any(check.status == BibleNumberingCheck.Status.REVIEWING for check in checks):
        return _('Under investigation')
    if any(check.status == BibleNumberingCheck.Status.UNCERTAIN for check in checks):
        return _('Still uncertain')
    return _('Not checked')
