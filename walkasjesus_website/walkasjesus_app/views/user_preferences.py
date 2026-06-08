from gettext import gettext
import hashlib
import json
import re
from pathlib import Path
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.core.cache import cache
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import translation
from django.views import View
from django.conf import settings
from google_trans import Translator
import requests

from walkasjesus_app.lib.access_policy import (
    filter_visible_bibles_for_request,
    is_bible_id_visible_for_request,
    is_david_stern_commentary_allowed,
    is_david_stern_source,
)
from walkasjesus_app.lib.sword_commentary import get_sword_source_config, normalize_book_key, sword_commentary_enabled, sword_disabled_source_ids
from walkasjesus_app.models import UserPreferences, BibleTranslation
from walkasjesus_app.models import SwordCommentarySource, SwordCommentaryEntry


COMMENTARY_TRANSLATION_CACHE_TIMEOUT = int(getattr(settings, 'COMMENTARY_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))
CROSS_DOMAIN_LANG_PARAM = '__waj_lang'
CROSS_DOMAIN_BIBLE_PARAM = '__waj_bible'
SCRIPTURA_SOURCE_TO_COMMENTATOR = {
    'david-stern': 'david-stern',
    'david_stern': 'david-stern',
    'jnt-stern': 'david-stern',
    'jnt_stern': 'david-stern',
    'stern': 'david-stern',
    'matthew-henry': 'matthew-henry',
    'matthew_henry': 'matthew-henry',
    'matthew-henry-nl': 'matthew-henry',
    'matthew_henry_nl': 'matthew-henry',
}


def _normalize_book_name(value):
    return normalize_book_key(value)


def _normalize_commentary_text(value):
    text = str(value or '').replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    if not text:
        return ''

    paragraphs = [part.strip() for part in text.split('\n\n') if part.strip()]
    deduped_paragraphs = []
    for part in paragraphs:
        if not deduped_paragraphs or deduped_paragraphs[-1] != part:
            deduped_paragraphs.append(part)
    return '\n\n'.join(deduped_paragraphs)


def _normalize_commentary_entry_key(value):
    if value in (None, ''):
        return '0'
    try:
        return str(int(value))
    except Exception:
        match = re.search(r'\d+', str(value))
        if match:
            return str(int(match.group(0)))
        return '0'


def _append_unique_commentary(existing_text, new_text):
    existing_normalized = _normalize_commentary_text(existing_text)
    new_normalized = _normalize_commentary_text(new_text)

    if not existing_normalized:
        return new_normalized
    if not new_normalized:
        return existing_normalized

    merged_parts = [part.strip() for part in existing_normalized.split('\n\n') if part.strip()]
    seen_parts = set(merged_parts)

    for part in [part.strip() for part in new_normalized.split('\n\n') if part.strip()]:
        if part not in seen_parts:
            merged_parts.append(part)
            seen_parts.add(part)

    return '\n\n'.join(merged_parts)


def _is_scriptura_commentator_disabled(source):
    normalized_source = str(source or '').strip().lower()
    if normalized_source in sword_disabled_source_ids():
        return True

    commentator_id = SCRIPTURA_SOURCE_TO_COMMENTATOR.get(str(source or '').strip().lower(), '')
    if not commentator_id:
        return False

    disabled_commentators = getattr(settings, 'COMMENTARY_DISABLED_SOURCES',
                                    getattr(settings, 'SCRIPTURA_DISABLED_COMMENTATORS', []))
    if not isinstance(disabled_commentators, (list, tuple, set)):
        return False
    disabled_set = {str(item).strip().lower() for item in disabled_commentators if str(item).strip()}
    return commentator_id in disabled_set


def _is_sword_source_enabled(source_id):
    if not sword_commentary_enabled():
        return False
    normalized_source = str(source_id or '').strip().lower()
    if not normalized_source:
        return False
    if not normalized_source.startswith('sword-'):
        return False
    if normalized_source in sword_disabled_source_ids():
        return False
    return SwordCommentarySource.objects.filter(source_id=source_id, is_enabled=True).exists()


def _local_sword_commentary(source_id, book, chapter):
    source = SwordCommentarySource.objects.filter(source_id=source_id, is_enabled=True).first()
    if not source:
        return {}

    book_key = _normalize_book_name(book)
    if not book_key:
        return {}

    entries = SwordCommentaryEntry.objects.filter(source=source, book_key=book_key, chapter=chapter).order_by('verse')
    payload = {}
    for entry in entries:
        text = _normalize_commentary_text(entry.text)
        if text:
            payload[str(entry.verse)] = text
    return payload


def _available_bibles_for_language(request, language_code):
    bible_translation = BibleTranslation()
    bibles = [b for b in bible_translation.all_enabled() if b.language == language_code]
    return filter_visible_bibles_for_request(request, bibles)


def _resolve_default_bible_id_for_language(request, language_code):
    fallback_any_id = settings.DEFAULT_BIBLE_ANY_LANGUAGE
    preferred_default_id = settings.DEFAULT_BIBLE_PER_LANGUAGE.get(language_code, fallback_any_id)

    if is_bible_id_visible_for_request(request, preferred_default_id):
        return preferred_default_id

    if is_bible_id_visible_for_request(request, fallback_any_id):
        return fallback_any_id

    visible_for_language = _available_bibles_for_language(request, language_code)
    if visible_for_language:
        return visible_for_language[0].id

    visible_any = filter_visible_bibles_for_request(request, BibleTranslation().all_enabled())
    if visible_any:
        return visible_any[0].id

    return ''


@lru_cache(maxsize=1)
def _load_local_david_stern_index():
    index = {}
    data_path = Path(__file__).resolve().parents[3] / 'bible_lib' / 'sources' / 'jnt_bible_lib_compatible.json'

    if not data_path.exists():
        return index

    try:
        with data_path.open('r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except Exception:
        return index

    for book in payload.get('books', []):
        aliases = {
            book.get('bible_book'),
            book.get('bible_book_enum_name'),
            book.get('bible_book_abbreviation'),
            book.get('book_title_source'),
        }

        for chapter in book.get('chapters', []):
            chapter_number = chapter.get('chapter_number')
            try:
                chapter_number = int(chapter_number)
            except Exception:
                continue

            entries = {}

            commentary_by_verse = chapter.get('commentary_by_verse') or {}
            for verse_key, verse_items in commentary_by_verse.items():
                text = ''
                if isinstance(verse_items, list):
                    for item in verse_items:
                        text = _append_unique_commentary(text, item)
                else:
                    text = _normalize_commentary_text(verse_items)
                if text:
                    entries[_normalize_commentary_entry_key(verse_key)] = text

            for section in chapter.get('commentary_sections') or []:
                verse_start = section.get('verse_start')
                entry_key = _normalize_commentary_entry_key(verse_start)

                text = _normalize_commentary_text(section.get('text'))
                if not text:
                    continue

                if entries.get(entry_key):
                    entries[entry_key] = _append_unique_commentary(entries[entry_key], text)
                else:
                    entries[entry_key] = text

            if not entries:
                continue

            for alias in aliases:
                normalized_alias = _normalize_book_name(alias)
                if normalized_alias:
                    index[f'{normalized_alias}|{chapter_number}'] = entries

    return index


def _local_david_stern_commentary(book, chapter):
    normalized_book = _normalize_book_name(book)
    if not normalized_book:
        return {}
    return _load_local_david_stern_index().get(f'{normalized_book}|{chapter}', {})


def _resolve_path_in_any_language(path):
    for code, _ in settings.LANGUAGES:
        with translation.override(code):
            try:
                return resolve(path)
            except Resolver404:
                continue
    return None


def _localized_next_url(next_url, language_code):
    fallback = '/'
    if not next_url:
        return fallback

    split = urlsplit(next_url)
    if split.scheme or split.netloc:
        return fallback
    path = split.path or '/'

    match = _resolve_path_in_any_language(path)
    if match is not None:
        try:
            with translation.override(language_code):
                localized_path = reverse(match.view_name, args=match.args, kwargs=match.kwargs)
            return urlunsplit(('', '', localized_path, split.query, split.fragment))
        except NoReverseMatch:
            pass

    # If the incoming path is already valid in the target language, keep it.
    with translation.override(language_code):
        try:
            resolve(path)
            return urlunsplit(('', '', path, split.query, split.fragment))
        except Resolver404:
            return fallback


def _absolute_redirect_for_language(request, language_code, redirect_url, selected_bible_id=''):
    # Keep relative redirects when domain mapping is not configured.
    if not redirect_url or redirect_url.startswith('http://') or redirect_url.startswith('https://'):
        return redirect_url

    nl_domain = getattr(settings, 'GEO_REDIRECT_NL_DOMAIN', '').strip()
    en_domain = getattr(settings, 'GEO_REDIRECT_EN_DOMAIN', '').strip()
    if not nl_domain or not en_domain:
        return redirect_url

    target_domain = nl_domain if language_code == 'nl' else en_domain
    host = request.get_host().split(':')[0]
    if host == target_domain:
        return redirect_url

    split = urlsplit(redirect_url)
    query_items = parse_qsl(split.query, keep_blank_values=True)
    query_items.append((CROSS_DOMAIN_LANG_PARAM, language_code))
    selected_bible_id = str(selected_bible_id or '').strip()
    if selected_bible_id:
        query_items.append((CROSS_DOMAIN_BIBLE_PARAM, selected_bible_id))
    redirect_url = urlunsplit(('', '', split.path or '/', urlencode(query_items, doseq=True), split.fragment))

    forwarded_proto = str(request.META.get('HTTP_X_FORWARDED_PROTO', '')).strip().lower()
    scheme = getattr(settings, 'GEO_REDIRECT_SCHEME', 'https')
    if request.is_secure():
        scheme = 'https'
    elif forwarded_proto in ('http', 'https'):
        scheme = forwarded_proto
    return f'{scheme}://{target_domain}{redirect_url}'


def _default_bible_for_language(request, language_code):
    default_bible_id = _resolve_default_bible_id_for_language(request, language_code)
    if not default_bible_id:
        return BibleTranslation().get(settings.DEFAULT_BIBLE_ANY_LANGUAGE)
    return BibleTranslation().get(default_bible_id)


def _preferred_bible_for_language(request, session, language_code):
    preferred_bibles = session.get(UserPreferences.PER_LANGUAGE_BIBLE_SESSION_KEY, {})
    if isinstance(preferred_bibles, dict):
        preferred_bible_id = str(preferred_bibles.get(language_code, '')).strip()
        if preferred_bible_id and is_bible_id_visible_for_request(request, preferred_bible_id):
            try:
                preferred_bible = BibleTranslation().get(preferred_bible_id)
                if preferred_bible.language == language_code:
                    return preferred_bible
            except Exception:
                pass
    return _default_bible_for_language(request, language_code)


def _default_media_languages_for_language(language_code):
    normalized = str(language_code or '').strip().lower()[:2]
    if normalized == 'nl':
        return ['en', 'nl']
    if normalized:
        return [normalized]
    return ['en']


class UserPreferencesLanguageSwitchView(View):
    """Switch UI language safely and return a localized redirect URL.

    This avoids 404 after language change when the current path slug differs per locale.
    """

    def post(self, request):
        language_code = str(request.POST.get('language', '')).strip().lower()
        next_url = request.POST.get('next', request.META.get('HTTP_REFERER', '/'))

        supported_languages = {code for code, _ in settings.LANGUAGES}
        if language_code not in supported_languages:
            return JsonResponse({'error': gettext('Unsupported language')}, status=400)

        # Keep selected bible aligned with the selected site language.
        requested_bible_id = str(request.POST.get('bible_id', '')).strip()
        bible = None
        if requested_bible_id and is_bible_id_visible_for_request(request, requested_bible_id):
            try:
                candidate = BibleTranslation().get(requested_bible_id)
                if candidate.language == language_code:
                    bible = candidate
            except Exception:
                bible = None

        if bible is None:
            bible = _preferred_bible_for_language(request, request.session, language_code)

        translation.activate(language_code)
        preferences = UserPreferences(request.session)
        preferences.bible = bible
        preferences.languages = _default_media_languages_for_language(language_code)

        redirect_url = _localized_next_url(next_url, language_code)
        redirect_url = _absolute_redirect_for_language(request, language_code, redirect_url, bible.id)
        response = JsonResponse({'redirect_url': redirect_url})
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            language_code,
            max_age=getattr(settings, 'LANGUAGE_COOKIE_AGE', None),
            path=getattr(settings, 'LANGUAGE_COOKIE_PATH', '/'),
            domain=getattr(settings, 'LANGUAGE_COOKIE_DOMAIN', None),
            secure=getattr(settings, 'LANGUAGE_COOKIE_SECURE', False),
            httponly=getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False),
            samesite=getattr(settings, 'LANGUAGE_COOKIE_SAMESITE', None),
        )
        return response


def _translate_commentary_text(text, target_language):
    try:
        translator = Translator()
        return translator.translate(text, src='en', dest=target_language).text
    except Exception:
        response = requests.get(
            'https://translate.googleapis.com/translate_a/single',
            params={
                'client': 'gtx',
                'sl': 'en',
                'tl': target_language,
                'dt': 't',
                'q': text,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        segments = data[0] if isinstance(data, list) and data else []
        translated_parts = [segment[0] for segment in segments if isinstance(segment, list) and segment and segment[0]]
        return ''.join(translated_parts)

class UserPreferencesBibleView(View):
    def post(self, request):
        bible_id = request.POST.get('bible_id')
        if bible_id:
            try:
                new_bible = BibleTranslation().get(bible_id)

                if not is_bible_id_visible_for_request(request, bible_id):
                    messages.error(request, gettext('The selected Bible translation is currently disabled.'))
                else:
                    UserPreferences(request.session).bible = new_bible
                    messages.success(request, gettext('Bible translation changed successfully.'))
            except BibleTranslation.DoesNotExist:
                messages.error(request, gettext('Bible translation not found.'))
        else:
            messages.error(request, gettext('Failed to change the Bible translation.'))

        return HttpResponseRedirect(request.POST.get('next', '/'))


class UserPreferencesLanguagesView(View):
    def post(self, request):
        redirect = HttpResponseRedirect(request.POST.get('next', '/'))

        if 'languages' not in request.POST:
            messages.error(request, gettext('Failed to change the user languages'))
            return redirect

        selected_languages = request.POST.getlist('languages')

        if selected_languages:
            UserPreferences(request.session).languages = selected_languages
            messages.success(request, gettext('Languages updated successfully.'))
        else:
            messages.error(request, gettext('No languages selected'))

        return redirect


class BibleTranslationsForLanguageView(View):
    """Returns JSON with Bible translations available for the given language code."""
    def get(self, request):
        language_code = request.GET.get('language', 'en')
        bibles = _available_bibles_for_language(request, language_code)
        default_bible_id = _resolve_default_bible_id_for_language(request, language_code)
        if default_bible_id and not any(b.id == default_bible_id for b in bibles):
            default_bible_id = bibles[0].id if bibles else ''
        return JsonResponse({
            'bibles': [{'id': b.id, 'name': b.name} for b in bibles],
            'default_bible_id': default_bible_id,
        })


class CommentaryTranslationView(View):
    """Machine-translates commentary text for the current UI language."""

    def post(self, request):
        text = str(request.POST.get('text', '')).strip()
        target_language = str(request.POST.get('target_language', 'en')).strip().lower()[:2]

        if not text:
            return JsonResponse({'translated_text': ''})

        if not target_language or target_language == 'en':
            return JsonResponse({'translated_text': text, 'language': 'en', 'machine_translated': False})

        digest = hashlib.sha256(f'{target_language}:{text}'.encode('utf-8')).hexdigest()
        cache_key = f'commentary_translation:v1:{digest}'
        cached = cache.get(cache_key)
        if cached is not None:
            return JsonResponse(cached)

        payload = {
            'translated_text': _translate_commentary_text(text, target_language),
            'language': target_language,
            'machine_translated': True,
        }
        cache.set(cache_key, payload, COMMENTARY_TRANSLATION_CACHE_TIMEOUT)
        return JsonResponse(payload)


class ScripturaCommentaryProxyView(View):
    """Proxy BijbelAPI commentary calls through Django to avoid browser CORS issues."""

    def get(self, request):
        source = str(request.GET.get('source', '')).strip()
        book = str(request.GET.get('book', '')).strip()
        chapter = str(request.GET.get('chapter', '')).strip()
        verse = str(request.GET.get('verse', '')).strip()

        if not source or not book or not chapter:
            return JsonResponse({'error': gettext('Missing commentary parameters')}, status=400)

        if _is_scriptura_commentator_disabled(source):
            return JsonResponse({'error': gettext('This commentator is disabled')}, status=404)

        if _is_sword_source_enabled(source):
            try:
                chapter_number = int(chapter)
            except Exception:
                return JsonResponse({'error': gettext('Invalid chapter parameter')}, status=400)
            return JsonResponse(_local_sword_commentary(source, book, chapter_number))

        if is_david_stern_source(source) and not is_david_stern_commentary_allowed(request):
            return JsonResponse({'error': gettext('Login required for this commentator')}, status=403)

        if is_david_stern_source(source):
            try:
                chapter_number = int(chapter)
            except Exception:
                return JsonResponse({'error': gettext('Invalid chapter parameter')}, status=400)

            return JsonResponse(_local_david_stern_commentary(book, chapter_number))

        headers = {}
        bijbel_api_key = str(getattr(settings, 'BIJBEL_API_KEY', '')).strip()
        if bijbel_api_key:
            headers['x-api-key'] = bijbel_api_key

        try:
            response = requests.get(
                str(getattr(settings, 'COMMENTARY_API_URL', 'https://www.bijbelapi.com/api/commentary')).strip(),
                params={
                    'source': source,
                    'book': book,
                    'chapter': chapter,
                    'verse': verse,
                },
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return JsonResponse(payload)
            return JsonResponse({}, safe=False)
        except Exception as exc:
            return JsonResponse({'error': str(exc)}, status=502)

