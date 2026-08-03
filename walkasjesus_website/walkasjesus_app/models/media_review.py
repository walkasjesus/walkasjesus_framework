from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from walkasjesus_app.models.law_of_messiah_media import MediaResource


class MediaReviewRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    )

    REJECTION_REASON_CHOICES = (
        ('too_many_resources', 'There are already too many other media resources for this step or law.'),
        ('not_in_line_with_preaching', 'The media resource is not in line with the preaching we can stand behind.'),
        ('not_compact_or_encouraging', 'The media resource is not compelling enough; we are looking for more compact, encouraging teaching.'),
    )

    resource = models.ForeignKey(MediaResource, on_delete=models.CASCADE, related_name='review_requests')
    applicant = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name='media_review_requests')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requested_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name='media_reviews_done')
    review_notes = models.TextField(blank=True, default='')
    rejection_reason = models.CharField(max_length=64, choices=REJECTION_REASON_CHOICES, blank=True, default='')
    history = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-requested_at', '-pk']
        verbose_name = 'Media review request'
        verbose_name_plural = 'Media review requests'
        permissions = [
            ('can_review_media_resources', 'Can review media resources'),
        ]

    def __str__(self):
        return f'{self.resource_id} - {self.status}'

    def add_history(self, message):
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f'{timestamp} - {message}'
        if self.history:
            self.history = f'{self.history}\n{entry}'
        else:
            self.history = entry
        self.save(update_fields=['history'])

    def approve(self, reviewer, notes=''):
        self.status = self.STATUS_APPROVED
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.rejection_reason = ''
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'review_notes', 'rejection_reason'])
        self.resource.is_public = True
        self.resource.save(update_fields=['is_public'])
        self.add_history(f'Approved by {reviewer.username}')

    def reject(self, reviewer, reason, notes=''):
        self.status = self.STATUS_REJECTED
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.rejection_reason = reason
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by', 'review_notes', 'rejection_reason'])
        self.resource.is_public = False
        self.resource.save(update_fields=['is_public'])
        self.add_history(f'Rejected by {reviewer.username}: {reason}')
