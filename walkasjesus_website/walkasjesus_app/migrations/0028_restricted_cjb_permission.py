from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0027_alter_maimonidesbiblereference_book_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bibletranslationmetadata',
            options={
                'permissions': [
                    ('view_restricted_cjb_translation', 'Can view the restricted Complete Jewish Bible translation'),
                ],
            },
        ),
    ]