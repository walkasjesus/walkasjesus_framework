from gettext import gettext
import hashlib

from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponseRedirect, JsonResponse
from django.views import View
from django.conf import settings
from google_trans import Translator
import requests

from walkasjesus_app.models import UserPreferences, BibleTranslation


COMMENTARY_TRANSLATION_CACHE_TIMEOUT = int(getattr(settings, 'COMMENTARY_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))


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

