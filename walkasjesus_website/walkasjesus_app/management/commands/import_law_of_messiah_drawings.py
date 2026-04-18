import os
import logging

from django.core.management import BaseCommand
from django.db import IntegrityError

from walkasjesus_app.models import LawOfMessiah, LawOfMessiahDrawing
from walkasjesus_website.settings import BASE_DIR


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Add drawings to Law of Messiah items. Filename must match the Law of Messiah ID.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--image-dir',
            type=str,
            default='media/images',
            help='The directory containing Law of Messiah drawing images (relative to BASE_DIR)'
        )
        parser.add_argument(
            '--author',
            type=str,
            default='Jenske Visser',
            help='The author name for the drawings'
        )

    def handle(self, *args, **options):
        image_dir = options['image_dir']
        author = options['author']
        
        # Build the full path to the images directory
        full_image_path = os.path.join(BASE_DIR, image_dir)
        
        if not os.path.isdir(full_image_path):
            self.stdout.write(
                self.style.ERROR(f'Directory not found: {full_image_path}')
            )
            return
        
        self.stdout.write(f'Scanning directory: {full_image_path}')
        
        added_count = 0
        skipped_count = 0
        
        # Get all PNG files
        for filename in sorted(os.listdir(full_image_path)):
            if not filename.lower().endswith('.png'):
                continue
            
            # Extract ID from filename (e.g., aa11.png -> AA11)
            lom_id = os.path.splitext(filename)[0].upper()
            
            try:
                # Check if Law of Messiah with this ID exists
                law_of_messiah = LawOfMessiah.objects.get(id=lom_id)
            except LawOfMessiah.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f'Skipped {filename}: Law of Messiah with ID "{lom_id}" not found'
                    )
                )
                skipped_count += 1
                continue
            
            # Build relative image URL (relative to MEDIA_ROOT)
            img_url = os.path.join(image_dir, filename).replace('\\', '/')
            
            try:
                # Try to get or create the drawing
                drawing, is_created = LawOfMessiahDrawing.objects.get_or_create(
                    law_of_messiah=law_of_messiah,
                    img_url=img_url,
                    defaults={
                        'author': author,
                        'title': f'Drawing for {lom_id}',
                        'is_public': True,
                    }
                )
                
                if is_created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Added drawing for {lom_id}: {filename}'
                        )
                    )
                    added_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Drawing already exists for {lom_id}: {filename}'
                        )
                    )
                    skipped_count += 1
                    
            except IntegrityError as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Failed to add drawing for {lom_id}: {str(e)}'
                    )
                )
                skipped_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error processing {filename}: {str(e)}'
                    )
                )
                skipped_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: Added {added_count} drawings, Skipped {skipped_count}'
            )
        )
