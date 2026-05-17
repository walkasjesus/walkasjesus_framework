from pathlib import Path

from django.conf import settings
from sorl.thumbnail import get_thumbnail


def normalize_media_relative_path(img_url):
    image_source_path = str(img_url or '').strip()
    if not image_source_path:
        return ''

    media_url = str(settings.MEDIA_URL or '').strip()
    if media_url and image_source_path.startswith(media_url):
        image_source_path = image_source_path[len(media_url):]

    if image_source_path.startswith('/'):
        image_source_path = image_source_path[1:]
    if image_source_path.startswith('media/'):
        image_source_path = image_source_path[len('media/'):]

    return image_source_path


def media_path_candidates(img_url):
    normalized_path = normalize_media_relative_path(img_url)
    if not normalized_path:
        return []

    candidates = [normalized_path]
    path = Path(normalized_path)
    basename = path.name
    parent = Path(settings.MEDIA_ROOT) / path.parent

    if basename and parent.exists() and parent.is_dir():
        suffix_matches = sorted(
            item for item in parent.iterdir()
            if item.is_file() and item.name.endswith(basename) and item.name != basename
        )
        candidates.extend(
            str(path.parent / item.name) if str(path.parent) != '.' else item.name
            for item in suffix_matches
        )

    deduped = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def resolve_media_relative_path(img_url):
    for candidate in media_path_candidates(img_url):
        if (Path(settings.MEDIA_ROOT) / candidate).is_file():
            return candidate
    return ''


def media_file_exists(img_url):
    return bool(resolve_media_relative_path(img_url))


def resolved_media_url(img_url):
    resolved_path = resolve_media_relative_path(img_url)
    if not resolved_path:
        return ''
    return f"{settings.MEDIA_URL}{resolved_path}"


def media_url_to_storage_path(url):
    candidate = str(url or '').strip()
    media_url = str(settings.MEDIA_URL or '').strip()
    if not candidate or not media_url or not candidate.startswith(media_url):
        return ''
    return candidate[len(media_url):]


def thumbnail_url_or_placeholder(img_url, geometry='620x877', quality=85):
    resolved_path = resolve_media_relative_path(img_url)
    if not resolved_path:
        return f"{settings.STATIC_URL}images/drawing_placeholder.png"

    thumbnail = get_thumbnail(resolved_path, geometry, quality=quality)
    thumbnail_storage_path = media_url_to_storage_path(thumbnail.url)
    if thumbnail_storage_path and not (Path(settings.MEDIA_ROOT) / thumbnail_storage_path).is_file():
        thumbnail = get_thumbnail(resolved_path, geometry, quality=quality, force=True)
    return thumbnail.url