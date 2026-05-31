from gettext import gettext
import hashlib
import json
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

from walkasjesus_app.models import UserPreferences, BibleTranslation


COMMENTARY_TRANSLATION_CACHE_TIMEOUT = int(getattr(settings, 'COMMENTARY_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))
CROSS_DOMAIN_LANG_PARAM = '__waj_lang'
CROSS_DOMAIN_BIBLE_PARAM = '__waj_bible'
LOCAL_DAVID_STERN_SOURCES = {
    'david-stern',
    'david_stern',
    'jnt-stern',
    'jnt_stern',
    'stern',
}


def _normalize_book_name(value):
    return ''.join(ch for ch in str(value or '').lower() if ch.isalnum())


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
                    text = '\n\n'.join(str(item).strip() for item in verse_items if str(item).strip())
                else:
                    text = str(verse_items or '').strip()
                if text:
                    entries[str(verse_key)] = text

            for section in chapter.get('commentary_sections') or []:
                verse_start = section.get('verse_start')
                entry_key = '0'
                if verse_start not in (None, ''):
                    try:
                        entry_key = str(int(verse_start))
                    except Exception:
                        entry_key = str(verse_start)

                text = str(section.get('text') or '').strip()
                if not text:
                    continue

                if entries.get(entry_key):
                    entries[entry_key] = f"{entries[entry_key]}\n\n{text}"
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


def _default_bible_for_language(language_code):
    default_bible_id = settings.DEFAULT_BIBLE_PER_LANGUAGE.get(language_code, settings.DEFAULT_BIBLE_ANY_LANGUAGE)
    if default_bible_id in settings.DISABLED_BIBLE_TRANSLATIONS:
        default_bible_id = settings.DEFAULT_BIBLE_ANY_LANGUAGE
    return BibleTranslation().get(default_bible_id)


def _preferred_bible_for_language(session, language_code):
    preferred_bibles = session.get(UserPreferences.PER_LANGUAGE_BIBLE_SESSION_KEY, {})
    if isinstance(preferred_bibles, dict):
        preferred_bible_id = str(preferred_bibles.get(language_code, '')).strip()
        if preferred_bible_id and preferred_bible_id not in settings.DISABLED_BIBLE_TRANSLATIONS:
            try:
                preferred_bible = BibleTranslation().get(preferred_bible_id)
                if preferred_bible.language == language_code:
                    return preferred_bible
            except Exception:
                pass
    return _default_bible_for_language(language_code)


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
        if requested_bible_id and requested_bible_id not in settings.DISABLED_BIBLE_TRANSLATIONS:
            try:
                candidate = BibleTranslation().get(requested_bible_id)
                if candidate.language == language_code:
                    bible = candidate
            except Exception:
                bible = None

        if bible is None:
            bible = _preferred_bible_for_language(request.session, language_code)

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
                
                # Check if the selected Bible is in the disabled list
                if bible_id in settings.DISABLED_BIBLE_TRANSLATIONS:
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
        bible_translation = BibleTranslation()
        bibles = [b for b in bible_translation.all_enabled() if b.language == language_code]
        default_bible_id = settings.DEFAULT_BIBLE_PER_LANGUAGE.get(language_code, settings.DEFAULT_BIBLE_ANY_LANGUAGE)
        if default_bible_id in settings.DISABLED_BIBLE_TRANSLATIONS:
            default_bible_id = settings.DEFAULT_BIBLE_ANY_LANGUAGE
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

        if source.lower() in LOCAL_DAVID_STERN_SOURCES:
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

