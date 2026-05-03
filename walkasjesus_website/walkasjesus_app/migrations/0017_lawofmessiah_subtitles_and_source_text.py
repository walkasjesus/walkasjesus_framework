from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0016_lawofmessiah_review_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='lawofmessiah',
            name='commandment_subtitles',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name='lawofmessiah',
            name='source',
            field=models.TextField(blank=True, default=''),
        ),
    ]
