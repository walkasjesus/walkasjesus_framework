from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0017_lawofmessiah_subtitles_and_source_text'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE commandments_app_lawofmessiah DROP COLUMN IF EXISTS manually_review;",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name='lawofmessiah',
                    name='manually_review',
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE commandments_app_lawofmessiah
                        ADD COLUMN IF NOT EXISTS related_lawofmessiah JSON NOT NULL DEFAULT (JSON_ARRAY());
                    """,
                    reverse_sql="ALTER TABLE commandments_app_lawofmessiah DROP COLUMN IF EXISTS related_lawofmessiah;",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='lawofmessiah',
                    name='related_lawofmessiah',
                    field=models.JSONField(blank=True, default=list),
                ),
            ],
        ),
    ]
