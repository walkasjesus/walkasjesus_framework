# Generated by Django 2.2.4 on 2019-08-24 07:39

import commandments_app.models
from django.db import migrations, models
import django.db.models.deletion
import url_or_relative_url_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0016_auto_20190815_1953'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commandment',
            name='category',
            field=models.CharField(choices=[('Salvation', 'Salvation Commands'), ('Discipleship', 'Discipleship Commands'), ('Worship', 'Worship Commands'), ('Blessings', 'Blessings'), ('JudgmentSeat', 'Judgment Seat Commands'), ('Relationship', 'Relationship Commands'), ('Marriage', 'Marriage Commands'), ('Persecution', 'Persecution Commands'), ('Thinking', 'Thinking Commands'), ('Prayer', 'Prayer Commands'), ('FalseTeachers', 'False Teachers Commands'), ('Witnessing', 'Witnessing Commands'), ('Greatest', 'Greatest Commands'), ('Finance', 'Finance Commands'), ('Holiness', 'Holiness Commands')], default=commandments_app.models.CommandmentCategories('Salvation Commands'), max_length=32),
        ),
        migrations.CreateModel(
            name='Blog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='', max_length=128)),
                ('author', models.CharField(default='', max_length=64)),
                ('url', url_or_relative_url_field.fields.URLOrRelativeURLField(default='#')),
                ('is_public', models.BooleanField(default=False)),
                ('commandment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='commandments_app.Commandment')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
