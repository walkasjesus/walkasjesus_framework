"""
Importer for Maimonides commandments from YAML source.
Usage: python manage.py import_maimonides
"""
import logging
import os
import yaml
from django.core.management.base import BaseCommand
from walkasjesus_app.models import Maimonides

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import Maimonides commandments from YAML file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default='data/lawofmessiah/volume_1_2_output/output_maimonides.yaml',
            help='Path to Maimonides YAML file',
        )

    def handle(self, *args, **options):
        source_path = options['source']
        if not os.path.exists(source_path):
            self.stdout.write(self.style.ERROR(f'File not found: {source_path}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Importing Maimonides from {source_path}'))

        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading YAML: {e}'))
            return

        commandments = data.get('commandments', [])
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for item in commandments:
            cmd_id = str(item.get('id', '')).strip()
            cmd_type = self._map_commandment_type(item.get('commandment_type', 'positive'))
            commandment_text = str(item.get('commandment', '')).strip()

            if not cmd_id:
                skipped_count += 1
                continue

            obj, created = Maimonides.objects.update_or_create(
                id=cmd_id,
                defaults={
                    'commandment_type': cmd_type,
                    'commandment': commandment_text,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Import complete: {created_count} created, {updated_count} updated, {skipped_count} skipped'
            )
        )

    def _map_commandment_type(self, value):
        """Map commandment type to model choice."""
        normalized = str(value or '').lower().strip()
        if 'negative' in normalized:
            return Maimonides.COMMANDMENT_TYPE_NEGATIVE
        return Maimonides.COMMANDMENT_TYPE_POSITIVE
