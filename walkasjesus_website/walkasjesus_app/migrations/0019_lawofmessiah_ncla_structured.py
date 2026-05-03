"""
Data migration: convert ncla from flat list ["JMm", "JFm", ...]
to structured list [{"group": "All", "codes": ["JMm", "JFm", ...]}].
"""
from django.db import migrations


def convert_ncla_to_structured(apps, schema_editor):
    LawOfMessiah = apps.get_model('commandments_app', 'LawOfMessiah')
    to_update = []
    for law in LawOfMessiah.objects.all():
        ncla = law.ncla
        if not ncla:
            continue
        # Already structured (list of dicts with 'codes' key)
        if isinstance(ncla, list) and ncla and isinstance(ncla[0], dict) and 'codes' in ncla[0]:
            continue
        # Old format: flat list of strings like ["JMm", "JFm", ...]
        if isinstance(ncla, list) and all(isinstance(c, str) for c in ncla):
            law.ncla = [{'group': 'All', 'codes': sorted(ncla)}]
            to_update.append(law)
    if to_update:
        LawOfMessiah.objects.bulk_update(to_update, ['ncla'])


def revert_ncla_to_flat(apps, schema_editor):
    LawOfMessiah = apps.get_model('commandments_app', 'LawOfMessiah')
    to_update = []
    for law in LawOfMessiah.objects.all():
        ncla = law.ncla
        if not ncla:
            continue
        if isinstance(ncla, list) and ncla and isinstance(ncla[0], dict):
            codes = []
            for group in ncla:
                codes.extend(group.get('codes', []))
            law.ncla = sorted(set(codes))
            to_update.append(law)
    if to_update:
        LawOfMessiah.objects.bulk_update(to_update, ['ncla'])


class Migration(migrations.Migration):

    dependencies = [
        ('commandments_app', '0018_lawofmessiah_related_unified_and_remove_manual'),
    ]

    operations = [
        migrations.RunPython(convert_ncla_to_structured, revert_ncla_to_flat),
    ]
