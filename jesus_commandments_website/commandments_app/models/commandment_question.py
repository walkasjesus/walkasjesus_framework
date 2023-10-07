from django.db import models

from commandments_app.models import Commandment


class Question(models.Model):
    """ Abstract base class for other media models. """
    commandment = models.ForeignKey(Commandment, on_delete=models.CASCADE, null=True, blank=True, default=None)
    text = models.CharField(max_length=256, default=None, blank=True, null=True)

    class Meta:
        unique_together = ['commandment', 'text']

    def __str__(self):
        return self.text
