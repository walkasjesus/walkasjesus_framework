from django.db import models


class Maimonides(models.Model):
    """Maimonides' 613 commandments - historical Jewish interpretation of Torah mitzvot."""

    COMMANDMENT_TYPE_POSITIVE = 'positive'
    COMMANDMENT_TYPE_NEGATIVE = 'negative'
    COMMANDMENT_TYPE_CHOICES = [
        (COMMANDMENT_TYPE_POSITIVE, 'Positive'),
        (COMMANDMENT_TYPE_NEGATIVE, 'Negative'),
    ]

    id = models.CharField(max_length=16, primary_key=True)
    commandment_type = models.CharField(max_length=32, choices=COMMANDMENT_TYPE_CHOICES, default=COMMANDMENT_TYPE_POSITIVE)
    commandment = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Maimonides commandment'
        verbose_name_plural = 'Maimonides Commandments'
        ordering = ['id']

    def __str__(self):
        return f'{self.id} - {self.commandment}'
