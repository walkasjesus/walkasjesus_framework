from urllib.parse import parse_qs, urlparse, urlunparse

import requests
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def is_youtube_url(url):
    host = urlparse(str(url or '').strip()).netloc.lower()
    return (
        'youtube.com' in host
        or 'youtu.be' in host
        or 'youtube-nocookie.com' in host
    )


def extract_youtube_video_id(url):
    parsed = urlparse(str(url or '').strip())
    host = parsed.netloc.lower()
    path = parsed.path or ''
    query = parse_qs(parsed.query, keep_blank_values=True)

    if 'youtu.be' in host:
        return path.lstrip('/').split('/')[0]

    if 'youtube.com' in host or 'youtube-nocookie.com' in host:
        if path == '/watch':
            return (query.get('v') or [''])[0]
        if path.startswith('/embed/'):
            return path.split('/embed/', 1)[1].split('/')[0]
        if path.startswith('/shorts/'):
            return path.split('/shorts/', 1)[1].split('/')[0]

    return ''


def normalize_youtube_embed_url(url):
    value = str(url or '').strip()
    if not value or not is_youtube_url(value):
        return value

    video_id = extract_youtube_video_id(value)
    if not video_id:
        return value

    parsed = urlparse(value)
    scheme = parsed.scheme or 'https'
    return urlunparse((scheme, 'www.youtube.com', f'/embed/{video_id}', '', '', ''))


def ensure_youtube_is_embeddable(url, timeout=5):
    value = str(url or '').strip()
    if not value or not is_youtube_url(value):
        return

    video_id = extract_youtube_video_id(value)
    if not video_id:
        raise ValidationError(_('Invalid YouTube URL format.'))

    watch_url = f'https://www.youtube.com/watch?v={video_id}'
    try:
        response = requests.get(
            'https://www.youtube.com/oembed',
            params={'url': watch_url, 'format': 'json'},
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; WalkAsJesusBot/1.0)'},
        )
    except requests.RequestException as exc:
        raise ValidationError(
            _('Could not validate this YouTube video for embedding right now: %(error)s')
            % {'error': str(exc)}
        )

    if response.status_code == 200:
        return

    if response.status_code in {401, 403, 404}:
        raise ValidationError(
            _('This YouTube video cannot be embedded. Please choose another video that allows embedding.')
        )

    raise ValidationError(
        _('Could not validate this YouTube video for embedding (HTTP %(status)s). Please try again.')
        % {'status': response.status_code}
    )
