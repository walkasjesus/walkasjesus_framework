# Generated by Django 4.2.5 on 2023-10-08 05:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0015_alter_biblereference_positive_negative_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lessondrawing',
            name='lesson',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='drawings', to='commandments_app.lesson'),
        ),
    ]
