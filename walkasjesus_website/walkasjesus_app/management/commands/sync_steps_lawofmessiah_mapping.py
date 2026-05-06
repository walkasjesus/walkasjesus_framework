from pathlib import Path

import yaml
from django.core.management.base import BaseCommand
from walkasjesus_app.models import LawOfMessiah, Commandment


class Command(BaseCommand):
    help = "Sync steps_lawofmessiah_mapping.yaml to populate related_steps ManyToMany field"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data/biblereferences/steps_lawofmessiah_mapping.yaml',
            help='Path to steps_lawofmessiah_mapping.yaml',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing related_steps before syncing',
        )

    def handle(self, *args, **options):
        mapping_file = Path(options['file'])
        
        if not mapping_file.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {mapping_file}"))
            return

        with open(mapping_file, 'r') as f:
            mappings = yaml.safe_load(f) or []

        if options['clear']:
            for law in LawOfMessiah.objects.all():
                law.related_steps.clear()
            self.stdout.write(self.style.SUCCESS("Cleared all related_steps"))

        created = 0
        updated = 0
        skipped = 0
        
        for mapping in mappings:
            step_id = mapping.get('step_id')
            law_id = mapping.get('lawofmessiah_id')
            
            if not step_id or not law_id:
                skipped += 1
                continue
            
            try:
                step = Commandment.objects.get(pk=int(step_id))
                law = LawOfMessiah.objects.get(pk=law_id)
                
                if law.related_steps.filter(pk=step.pk).exists():
                    self.stdout.write(f"  ✓ Step {step_id} already linked to Law {law_id}")
                    updated += 1
                else:
                    law.related_steps.add(step)
                    self.stdout.write(self.style.SUCCESS(f"✓ Linked Step {step_id} to Law {law_id}"))
                    created += 1
            except (Commandment.DoesNotExist, LawOfMessiah.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(f"✗ Skipped Step {step_id} → Law {law_id}: {str(e)}"))
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"\nSummary:"))
        self.stdout.write(f"  Created: {created}")
        self.stdout.write(f"  Updated: {updated}")
        self.stdout.write(f"  Skipped: {skipped}")
