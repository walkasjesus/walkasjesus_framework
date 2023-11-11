from django.db import models

from commandments_app.models import Lesson

class LessonQuestion(models.Model):
    """ Abstract base class for other media models. """
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True, default=None)
    text = models.CharField(max_length=256, default=None, blank=True, null=True)

    class Meta:
        unique_together = ['lesson', 'text']

    def __str__(self):
        return self.text
