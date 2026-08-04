from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django import template
from django.utils.translation import get_language
from walkasjesus_app.lib.youtube_embed_validation import is_youtube_url, normalize_youtube_embed_url

register = template.Library()


def _normalize_language_code(language_code):
    if not language_code:
        return "en"

    normalized = str(language_code).split("-")[0].split("_")[0].lower()
    return normalized if len(normalized) == 2 else "en"


@register.filter(name="youtube_captions_url")
def youtube_captions_url(url, language_code=None):
    if not url:
        return url

    url = str(url)
    if not is_youtube_url(url):
        return url

    url = normalize_youtube_embed_url(url)
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["cc_load_policy"] = ["1"]
    active_language = language_code or get_language()
    query["cc_lang_pref"] = [_normalize_language_code(active_language)]

    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))