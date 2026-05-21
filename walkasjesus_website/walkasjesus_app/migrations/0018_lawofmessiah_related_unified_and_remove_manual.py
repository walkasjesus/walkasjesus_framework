from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0017_lawofmessiah_subtitles_and_source_text'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lawofmessiah',
            name='manually_review',
        ),
    ]
