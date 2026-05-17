from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0021_lawofmessiahdrawing_media_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='lawofmessiahdrawing',
            name='commandment',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shared_media_resources', to='commandments_app.commandment'),
        ),
        migrations.AddField(
            model_name='lawofmessiahdrawing',
            name='lesson',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shared_media_resources', to='commandments_app.lesson'),
        ),
        migrations.AlterUniqueTogether(
            name='lawofmessiahdrawing',
            unique_together={('law_of_messiah', 'commandment', 'lesson', 'media_type', 'title', 'url', 'img_url', 'author', 'language', 'target_audience')},
        ),
    ]
