from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create a dedicated media contributor group with just the permissions needed to add media resources.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='The username of the user to assign to the group.')

    def handle(self, *args, **options):
        username = options['username']
        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        if not user:
            self.stderr.write(self.style.ERROR(f'User {username} not found.'))
            return

        group, _ = Group.objects.get_or_create(name='Media Contributors')
        permissions = [
            Permission.objects.get(codename='add_mediaresource', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='change_mediaresource', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='view_mediaresource', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='view_commandment', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='view_lesson', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='view_lawofmessiah', content_type__app_label='commandments_app'),
        ]
        group.permissions.set(permissions)
        group.save()

        user.groups.add(group)
        user.is_staff = True
        user.is_active = True
        user.save()

        self.stdout.write(self.style.SUCCESS(f'Assigned {username} to the Media Contributors group.'))
