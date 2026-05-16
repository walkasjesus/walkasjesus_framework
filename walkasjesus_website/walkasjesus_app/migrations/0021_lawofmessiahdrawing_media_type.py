from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0020_maimonides'),
    ]

    operations = [
        migrations.AddField(
            model_name='lawofmessiahdrawing',
            name='media_type',
            field=models.CharField(
                choices=[
                    ('drawing', 'Drawing'),
                    ('song', 'Song'),
                    ('superbook', 'Superbook'),
                    ('henkieshow', 'Henkieshow'),
                    ('movie', 'Movie'),
                    ('shortmovie', 'ShortMovie'),
                    ('wajvideo', 'WaJVideo'),
                    ('sermon', 'Sermon'),
                    ('picture', 'Picture'),
                    ('testimony', 'Testimony'),
                    ('blog', 'Blog'),
                    ('book', 'Book'),
                ],
                default='drawing',
                max_length=32,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='lawofmessiahdrawing',
            unique_together={
                ('law_of_messiah', 'media_type', 'title', 'url', 'img_url', 'author', 'language', 'target_audience')
            },
        ),
    ]
