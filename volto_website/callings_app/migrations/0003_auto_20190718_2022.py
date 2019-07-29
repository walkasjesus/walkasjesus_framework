# Generated by Django 2.2.3 on 2019-07-18 18:22
from bible_lib import BibleBooks
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('callings_app', '0002_auto_20190718_2013'),
    ]

    operations = [
        migrations.AlterField(
            model_name='biblereference',
            name='book',
            field=models.CharField(choices=[('Genesis', 'Genesis'), ('Exodus', 'Exodus'), ('Leviticus', 'Leviticus'), ('Numbers', 'Numbers'), ('Deuteronomy', 'Deuteronomy'), ('Joshua', 'Joshua'), ('Judges', 'Judges'), ('Ruth', 'Ruth'), ('SamuelFirstBook', '1 Samuel'), ('SamuelSecondBook', '2 Samuel'), ('KingsFirstBook', '1 Kings'), ('KingsSecondBook', '2 Kings'), ('ChroniclesFirstBook', '1 Chronicles'), ('ChroniclesSecondBook', '2 Chronicles'), ('Ezra', 'Ezra'), ('Nehemiah', 'Nehemiah'), ('Esther', 'Esther'), ('Job', 'Job'), ('Psalms', 'Psalms'), ('Proverbs', 'Proverbs'), ('Ecclesiastes', 'Ecclesiastes'), ('SongOfSolomon', 'Song of Solomon'), ('Isaiah', 'Isaiah'), ('Jeremiah', 'Jeremiah'), ('Lamentations', 'Lamentations'), ('Ezekiel', 'Ezekiel'), ('Daniel', 'Daniel'), ('Hosea', 'Hosea'), ('Joel', 'Joel'), ('Amos', 'Amos'), ('Obadiah', 'Obadiah'), ('Jonah', 'Jonah'), ('Micah', 'Micah'), ('Nahum', 'Nahum'), ('Habakkuk', 'Habakkuk'), ('Zephaniah', 'Zephaniah'), ('Haggai', 'Haggai'), ('Zechariah', 'Zechariah'), ('Malachi', 'Malachi'), ('Matthew', 'Matthew'), ('Mark', 'Mark'), ('Luke', 'Luke'), ('John', 'John'), ('Acts', 'Acts (of the Apostles)'), ('Romans', 'Romans'), ('CorinthiansFirstBook', '1 Corinthians'), ('CorinthiansSecondBook', '2 Corinthians'), ('Galatians', 'Galatians'), ('Ephesians', 'Ephesians'), ('Philippians', 'Philippians'), ('Colossians', 'Colossians'), ('ThessaloniansFirstBook', '1 Thessalonians'), ('ThessaloniansSecondBook', '2 Thessalonians'), ('TimothyFirstBook', '1 Timothy'), ('TimothySecondBook', '2 Timothy'), ('Titus', 'Titus'), ('Philemon', 'Philemon'), ('Hebrews', 'Hebrews'), ('James', 'James'), ('PeterFirstBook', '1 Peter'), ('PeterSecondBook', '2 Peter'), ('JohnFirstBook', '1 John'), ('JohnSecondBook', '2 John'), ('JohnThirdBook', '3 John'), ('Jude', 'Jude'), ('Revelation', 'Revelation')], default=BibleBooks('Genesis'), max_length=32),
        ),
    ]
