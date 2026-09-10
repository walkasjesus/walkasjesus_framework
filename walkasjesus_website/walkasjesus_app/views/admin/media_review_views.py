from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from walkasjesus_app.lib.youtube_embed_validation import ensure_youtube_is_embeddable, normalize_youtube_embed_url
from walkasjesus_app.models import Commandment, LawOfMessiah, MediaResource
from walkasjesus_app.models.media_review import MediaReviewRequest
from walkasjesus_app.models.law_of_messiah_media import LawOfMessiahDrawing

# Media types every step should have at least one of; shown first in the coverage report.
MEDIA_COVERAGE_PRIORITY_TYPES = [
    LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE,
    LawOfMessiahDrawing.MEDIA_TYPE_SERMON,
    LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY,
]
MEDIA_COVERAGE_EXTRA_TYPES = [
    LawOfMessiahDrawing.MEDIA_TYPE_MOVIE,
    LawOfMessiahDrawing.MEDIA_TYPE_WAJVIDEO,
    LawOfMessiahDrawing.MEDIA_TYPE_BLOG,
    LawOfMessiahDrawing.MEDIA_TYPE_BOOK,
]


def user_can_review_media_resources(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return user.has_perm('commandments_app.can_review_media_resources') or user.has_perm('walkasjesus_app.can_review_media_resources')


class MediaReviewDashboardView(View):
    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        pending_requests = MediaReviewRequest.objects.filter(status=MediaReviewRequest.STATUS_PENDING).select_related('resource', 'applicant', 'reviewed_by')
        reviewed_requests = MediaReviewRequest.objects.exclude(status=MediaReviewRequest.STATUS_PENDING).select_related('resource', 'applicant', 'reviewed_by')[:100]

        resources = MediaResource.objects.filter(is_public=False).select_related('commandment', 'lesson', 'law_of_messiah')
        counts = {
            'private_resources': resources.count(),
            'pending_reviews': pending_requests.count(),
            'total_resources': MediaResource.objects.count(),
        }

        return render(request, 'admin/media_review_dashboard.html', {
            'pending_requests': pending_requests,
            'reviewed_requests': reviewed_requests,
            'resources': resources,
            'counts': counts,
            'media_type_choices': LawOfMessiahDrawing.MEDIA_TYPE_CHOICES,
            'target_audience_choices': [('any', 'any'), ('adults', 'adults'), ('kids', 'kids')],
            'language_choices': [
                ('any', 'Language independent'),
                ('unknown', 'Language unknown'),
            ] + list(settings.LANGUAGES),
        })

    def post(self, request):
        if not user_can_review_media_resources(request.user):
            messages.error(request, 'You do not have permission to review media resources.')
            return redirect('admin:media_review_dashboard')

        request_id = request.POST.get('request_id')
        action = request.POST.get('action', '')
        review_notes = (request.POST.get('review_notes') or '').strip()
        rejection_reason = (request.POST.get('rejection_reason') or '').strip()

        review_request = MediaReviewRequest.objects.filter(pk=request_id).select_related('resource', 'applicant').first()
        if not review_request:
            messages.error(request, 'The review request was not found.')
            return redirect('admin:media_review_dashboard')

        resource = review_request.resource
        for field_name in ['title', 'description', 'author', 'media_type', 'target_audience', 'language', 'img_url', 'url']:
            value = request.POST.get(field_name, '')
            if value != '' or field_name in request.POST:
                setattr(resource, field_name, value)

        try:
            if resource.url:
                ensure_youtube_is_embeddable(resource.url)
                resource.url = normalize_youtube_embed_url(resource.url)
            resource.save()
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return redirect('admin:media_review_dashboard')

        if action == 'approve':
            review_request.approve(request.user, review_notes)
            self._send_mail(review_request.applicant, 'approved', review_request)
            messages.success(request, 'The media resource was approved and made public.')
        elif action == 'reject':
            if not rejection_reason:
                messages.error(request, 'Please choose a rejection reason.')
                return redirect('admin:media_review_dashboard')
            review_request.reject(request.user, rejection_reason, review_notes)
            self._send_mail(review_request.applicant, 'rejected', review_request)
            messages.success(request, 'The media resource was rejected and returned to the requester.')
        else:
            messages.error(request, 'Unknown action.')
            return redirect('admin:media_review_dashboard')

        return redirect('admin:media_review_dashboard')

    def _send_mail(self, recipient, outcome, review_request):
        if not recipient or not getattr(recipient, 'email', ''):
            return

        resource = review_request.resource
        if outcome == 'approved':
            subject = 'Your media resource was approved and published'
            message = (
                f'Hello,\n\n'
                f'Your media resource "{resource.title}" has been approved and is now public.\n\n'
                f'Review notes: {review_request.review_notes or "No notes provided"}\n'
            )
        else:
            subject = 'Your media resource was not approved'
            message = (
                f'Hello,\n\n'
                f'Your media resource "{resource.title}" was not approved.\n\n'
                f'Reason: {review_request.get_rejection_reason_display()}\n'
                f'Review notes: {review_request.review_notes or "No notes provided"}\n'
            )

        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient.email], fail_silently=True)


class MediaReviewReportView(View):
    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        requests = MediaReviewRequest.objects.select_related('resource', 'applicant', 'reviewed_by').order_by('-requested_at')
        return render(request, 'admin/media_review_report.html', {'requests': requests})


class MediaCoverageReportView(View):
    """Overview of which media types are still missing per step and per Law of Messiah item (public resources only)."""

    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        only_missing = request.GET.get('only_missing', '1') != '0'
        all_types = MEDIA_COVERAGE_PRIORITY_TYPES + MEDIA_COVERAGE_EXTRA_TYPES

        def _counts_by(field_name):
            counts = {}
            for row in (
                MediaResource.objects
                .filter(**{f'{field_name}__isnull': False}, is_public=True, media_type__in=all_types)
                .values(field_name, 'media_type')
                .annotate(total=Count('id'))
            ):
                counts.setdefault(row[field_name], {})[row['media_type']] = row['total']
            return counts

        counts_by_commandment = _counts_by('commandment_id')
        counts_by_law = _counts_by('law_of_messiah_id')

        def _build_row(item_id, title, admin_url_name, counts, kind):
            missing_priority = [
                media_type for media_type in MEDIA_COVERAGE_PRIORITY_TYPES
                if not counts.get(media_type)
            ]
            columns = [
                {'count': counts.get(media_type, 0), 'missing': media_type in missing_priority}
                for media_type in all_types
            ]
            return {
                'kind': kind,
                'id': item_id,
                'title': title,
                'change_url': reverse(admin_url_name, args=[item_id]),
                'columns': columns,
                'total': sum(column['count'] for column in columns),
                'missing_priority': missing_priority,
            }

        all_rows = []
        missing_total = 0
        for commandment in Commandment.objects.order_by('id'):
            row = _build_row(
                commandment.id, commandment.title, 'admin:commandments_app_commandment_change',
                counts_by_commandment.get(commandment.id, {}), 'Step',
            )
            if row['missing_priority']:
                missing_total += 1
            all_rows.append(row)

        for law in LawOfMessiah.objects.order_by('id'):
            row = _build_row(
                law.id, law.title, 'admin:commandments_app_lawofmessiah_change',
                counts_by_law.get(law.id, {}), 'Law',
            )
            if row['missing_priority']:
                missing_total += 1
            all_rows.append(row)

        if only_missing:
            all_rows = [row for row in all_rows if row['missing_priority']]

        # Least covered items first by default, so gaps are easy to spot.
        all_rows.sort(key=lambda row: row['total'])

        return render(request, 'admin/media_coverage_report.html', {
            'rows': all_rows,
            'priority_types': MEDIA_COVERAGE_PRIORITY_TYPES,
            'extra_types': MEDIA_COVERAGE_EXTRA_TYPES,
            'only_missing': only_missing,
            'missing_count': missing_total,
            'total_count': Commandment.objects.count() + LawOfMessiah.objects.count(),
        })
