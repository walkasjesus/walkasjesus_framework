from django.contrib.auth.models import User

admins = [('admin', 'admin', 'admin@email.com')]

for name, password, email in admins:
    User.objects.create_superuser(name, password, email)
