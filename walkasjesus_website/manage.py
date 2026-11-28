#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    # Apply before Django imports models, which also load the Bible catalogue.
    if len(sys.argv) > 1 and sys.argv[1] == 'check_bible_numbering':
        os.environ['BIBLE_API_OFFLINE'] = '1'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'walkasjesus_website.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
