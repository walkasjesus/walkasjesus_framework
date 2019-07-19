from django.contrib.auth.models import User

admins = [('admin', 'admin', 'admin@email.com')]

[User.objects.create_superuser(name, password, email) for name, password, email in admins]
