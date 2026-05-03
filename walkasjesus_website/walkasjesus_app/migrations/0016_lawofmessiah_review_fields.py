from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0015_lawofmessiah_related_steps'),
    ]

    operations = [
        migrations.AddField(
            model_name='lawofmessiah',
            name='double_ids',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='lawofmessiah',
            name='is_unique',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='lawofmessiah',
            name='manually_review',
            field=models.TextField(blank=True, default=''),
        ),
    ]
