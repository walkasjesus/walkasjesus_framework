from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0022_shared_media_resource_links'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commandment',
            name='category',
            field=models.CharField(blank=True, default='', max_length=256),
        ),
    ]