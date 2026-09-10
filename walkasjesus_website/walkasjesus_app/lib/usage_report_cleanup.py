from collections import defaultdict


def delete_legacy_hash_only_rows(model):
    """Delete rows with no ip_address on record (recorded before IP tracking existed)."""
    deleted, _ = model.objects.filter(ip_address__isnull=True).delete()
    return deleted


def consolidate_rows_by_ip(model, group_fields, count_fields):
    """Merge rows that share the same IP address (and group_fields) into a single row.

    Sums count_fields so totals stay unchanged; only reduces the number of rows shown
    per IP address (e.g. multiple sessions/user_keys from the same IP on the same day).
    """
    groups = defaultdict(list)
    for row in model.objects.filter(ip_address__isnull=False).order_by('pk'):
        key = tuple(getattr(row, field) for field in group_fields) + (row.ip_address,)
        groups[key].append(row)

    merged_rows = 0
    for rows in groups.values():
        if len(rows) <= 1:
            continue
        primary, *duplicates = rows
        for duplicate in duplicates:
            for count_field in count_fields:
                setattr(primary, count_field, getattr(primary, count_field) + getattr(duplicate, count_field))
            if getattr(duplicate, 'user_kind', None) == model.USER_AUTHENTICATED:
                primary.user_kind = model.USER_AUTHENTICATED
            duplicate.delete()
            merged_rows += 1
        primary.save(update_fields=list(count_fields) + ['user_kind', 'updated_at'])
    return merged_rows
