from django.db import models

from commandments_app.models import Commandment, Lesson


class Question(models.Model):
    """" Abstract base class for other media models. """
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    text = models.CharField(max_length=256, default=None, blank=True, null=True)

    class Meta:
        unique_together = ['commandment', 'text']

    def __str__(self):
        return self.text
