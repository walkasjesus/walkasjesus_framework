from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0033_alter_mediareviewrequest_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bibletranslationusagedaily',
            name='endpoint',
            field=models.CharField(
                choices=[
                    ('study_page', 'Bible Study page'),
                    ('verses_api', 'Bible Study verses API'),
                    ('search_api', 'Bible Study search API'),
                    ('commandment_verses', 'Commandment verses API'),
                    ('lesson_verses', 'Lesson verses API'),
                    ('law_of_messiah_verses', 'Law of Messiah verses API'),
                    ('maimonides_verses', 'Maimonides verses API'),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name='bibletranslationusagedaily',
            name='source',
            field=models.CharField(
                choices=[('api', 'API'), ('cache', 'Cache'), ('blocked', 'Blocked')],
                db_index=True,
                max_length=16,
            ),
        ),
    ]