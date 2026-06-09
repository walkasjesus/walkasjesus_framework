import logging
import re
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import translation
from django.views import View

from walkasjesus_app.lib.access_policy import is_bible_id_visible_for_request
from walkasjesus_app.models import Commandment, UserPreferences, Lesson, BibleTranslation, LawOfMessiah, LawOfMessiahDrawing


LOGGER = logging.getLogger(__name__)
STEPS_LOM_MAPPING_FILE = Path(__file__).resolve().parents[2] / 'data' / 'biblereferences' / 'steps_lawofmessiah_mapping.yaml'
VERSE_CACHE_TIMEOUT = int(getattr(settings, 'BIBLE_API_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))


def _normalize_law_id(law_id):
    normalized = str(law_id or '').strip().upper()
    match = re.match(r'^([A-Z]+)(\d+)$', normalized)
    if not match:
        return normalized

    prefix, number = match.groups()
    return f'{prefix}{int(number)}'


def _extract_related_law_ids(related_items):
    ids = []
    for related in related_items or []:
        if isinstance(related, dict):
            related_id = str(related.get('id', '')).strip()
        else:
            related_id = str(related).strip()
        if related_id:
            ids.append(_normalize_law_id(related_id))
    return ids


@lru_cache(maxsize=1)
def _step_to_law_mapping():
    if not STEPS_LOM_MAPPING_FILE.exists():
        return {}

    try:
        with open(STEPS_LOM_MAPPING_FILE, 'r', encoding='utf-8') as handle:
            rows = yaml.safe_load(handle) or []
    except Exception as exc:
        LOGGER.exception('Failed to read steps to Law of Messiah mapping: %s', exc)
        return {}

    mapping = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        step_id = str(row.get('step_id', '')).strip()
        law_id = _normalize_law_id(row.get('lawofmessiah_id', ''))
        if step_id and law_id:
            mapping[step_id] = law_id
    return mapping


class DetailView(View):
    def get(self, request, commandment_id: int):
        commandment = get_object_or_404(Commandment, pk=commandment_id)
        selected_bible = UserPreferences(request.session).bible
        cached_copyright = cache.get(_bible_copyright_cache_key(selected_bible))
        if cached_copyright:
            selected_bible.copyright = cached_copyright
        commandment.bible = selected_bible
        commandment.languages = UserPreferences(request.session).languages

        mapped_law_id = _step_to_law_mapping().get(str(commandment.id))
        mapped_law = None
        mapped_related_laws = []
        if mapped_law_id:
            mapped_law = LawOfMessiah.objects.filter(pk=mapped_law_id).first()
            if mapped_law:
                related_values = mapped_law.related_lawofmessiah or []
                if not related_values:
                    related_values = (mapped_law.commandments_related_ot or []) + (mapped_law.commandments_related_nt or [])

                related_ids = [
                    item_id for item_id in _extract_related_law_ids(related_values)
                    if item_id != mapped_law.id
                ]
                related_law_map = {
                    item.id: item
                    for item in LawOfMessiah.objects.filter(id__in=related_ids).order_by('id')
                }
                mapped_related_laws = [related_law_map[item_id] for item_id in related_ids if item_id in related_law_map]

        shared_media_by_type = _filter_grouped_media_by_audience(
            _collect_shared_media_by_type(commandment=commandment),
            _allowed_target_audiences(request),
            _allowed_media_languages(request),
        )
        shared_media_by_type = _enforce_kids_only_media_types(shared_media_by_type, _is_kids_mode(request))
        _apply_shared_media_to_commandment_display(commandment, shared_media_by_type)

        return render(
            request,
            'commandments/detail.html',
            {
                'commandment': commandment,
                'bible': selected_bible,
                'mapped_lawofmessiah': mapped_law,
                'mapped_related_lawofmessiah': mapped_related_laws,
                'shared_media_by_type': shared_media_by_type,
            },
        )


class DetailLessonView(View):
    def get(self, request, lesson_id: int):
        lesson = get_object_or_404(Lesson, pk=lesson_id)
        selected_bible = UserPreferences(request.session).bible
        cached_copyright = cache.get(_bible_copyright_cache_key(selected_bible))
        if cached_copyright:
            selected_bible.copyright = cached_copyright
        lesson.bible = selected_bible
        lesson.languages = UserPreferences(request.session).languages
        shared_media_by_type = _filter_grouped_media_by_audience(
            _collect_shared_media_by_type(commandment=lesson.commandment, lesson=lesson),
            _lesson_allowed_target_audiences(),
            _allowed_media_languages(request),
        )
        _apply_shared_media_to_lesson_display(lesson, shared_media_by_type)

        return render(request, 'lessons/detail.html', {
            'lesson': lesson,
            'bible': selected_bible,
            'shared_media_by_type': shared_media_by_type,
        })


def _shared_media_types():
    return [choice[0] for choice in LawOfMessiahDrawing.MEDIA_TYPE_CHOICES]


def _allowed_target_audiences(request):
    if _is_kids_mode(request):
        return {'any', 'kids'}
    return {'any', 'adults'}


def _is_kids_mode(request):
    return bool(request.COOKIES.get('jc_kids_mode'))


def _lesson_allowed_target_audiences():
    # Lessons are always child-focused pages.
    return {'any', 'kids'}


def _allowed_media_languages(request):
    current_language = str(translation.get_language() or '').strip().lower()[:2]
    if current_language == 'nl':
        return {'any', 'unknown', 'nl', 'en'}
    if current_language:
        return {'any', 'unknown', current_language}
    return {'any', 'unknown', 'en'}


def _media_target_audience(item):
    if isinstance(item, dict):
        return item.get('target_audience') or 'any'
    return getattr(item, 'target_audience', 'any') or 'any'


def _media_language(item):
    if isinstance(item, dict):
        return str(item.get('language') or 'any').strip().lower() or 'any'
    return str(getattr(item, 'language', 'any') or 'any').strip().lower() or 'any'


def _media_attr(item, key):
    if isinstance(item, dict):
        return str(item.get(key) or '').strip()
    return str(getattr(item, key, '') or '').strip()


def _is_displayable_media(item, media_type):
    title = _media_attr(item, 'title')
    description = _media_attr(item, 'description')
    url = _media_attr(item, 'url')
    img_url = _media_attr(item, 'img_url')

    if media_type in {
        LawOfMessiahDrawing.MEDIA_TYPE_SONG,
        LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK,
        LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW,
        LawOfMessiahDrawing.MEDIA_TYPE_MOVIE,
        LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE,
        LawOfMessiahDrawing.MEDIA_TYPE_WAJVIDEO,
        LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY,
        LawOfMessiahDrawing.MEDIA_TYPE_SERMON,
    }:
        return bool(url)

    if media_type in {
        LawOfMessiahDrawing.MEDIA_TYPE_DRAWING,
        LawOfMessiahDrawing.MEDIA_TYPE_PICTURE,
    }:
        return bool(img_url)

    return bool(title or description or url or img_url)


def _filter_grouped_media_by_audience(grouped, allowed_target_audiences, allowed_languages=None):
    if allowed_languages is None:
        allowed_languages = {'any', 'unknown', 'en'}
    return {
        media_type: [
            item for item in items
            if _media_target_audience(item) in allowed_target_audiences
            and _media_language(item) in allowed_languages
            and _is_displayable_media(item, media_type)
        ]
        for media_type, items in grouped.items()
    }


def _enforce_kids_only_media_types(grouped, kids_mode):
    if kids_mode:
        return grouped

    grouped[LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK] = []
    grouped[LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW] = []
    return grouped


def _collect_shared_media_by_type(commandment=None, lesson=None):
    grouped = {media_type: [] for media_type in _shared_media_types()}
    seen = set()

    def media_key(media):
        normalized_title = str(media.title or '').strip().lower()
        normalized_author = str(media.author or '').strip().lower()
        fallback_locator = (
            str(media.url or '').strip().lower(),
            str(media.img_url or '').strip().lower(),
        )
        return (
            media.media_type,
            normalized_title,
            normalized_author,
            fallback_locator if not (normalized_title or normalized_author) else '',
        )

    query = LawOfMessiahDrawing.objects.none()
    if commandment is not None:
        query = query | LawOfMessiahDrawing.objects.filter(commandment=commandment)
    if lesson is not None:
        query = query | LawOfMessiahDrawing.objects.filter(lesson=lesson)

    for media in query.distinct().order_by('media_type', 'id'):
        key = media_key(media)
        if key in seen:
            continue
        seen.add(key)
        grouped[media.media_type].append(media)
    return grouped


def _apply_shared_media_to_commandment_display(commandment, grouped):
    commandment.drawings = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_DRAWING, [])
    commandment.songs = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_SONG, [])
    commandment.superbooks = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK, [])
    commandment.henkieshows = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW, [])
    commandment.movies = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_MOVIE, [])
    commandment.short_movies = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE, [])
    commandment.waj_video = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_WAJVIDEO, [])
    commandment.sermons = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_SERMON, [])
    commandment.pictures = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_PICTURE, [])
    commandment.testimonies = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY, [])
    commandment.blogs = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_BLOG, [])
    commandment.books = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_BOOK, [])
    commandment.background_drawing = commandment.drawings[0] if commandment.drawings else ''


def _apply_shared_media_to_lesson_display(lesson, grouped):
    lesson.drawings = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_DRAWING, [])
    lesson.songs = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_SONG, [])
    lesson.superbooks = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK, [])
    lesson.henkieshows = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW, [])
    lesson.short_movies = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE, [])
    lesson.pictures = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_PICTURE, [])
    lesson.testimonies = grouped.get(LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY, [])
    lesson.background_drawing = lesson.drawings[0] if lesson.drawings else ''


def _collect_verses(bible, references, key_builder=None, verse_sources=None):
    """Fetch verse texts for a list of references using the given bible."""
    if key_builder is None:
        key_builder = lambda ref: str(ref.pk)

    verses = {}
    for ref in references:
        text, source = _get_or_fetch_verse_text_with_source(bible, ref)
        ref_key = key_builder(ref)
        verses[ref_key] = text if text else ''
        if verse_sources is not None:
            verse_sources[ref_key] = source
    return verses


def _reference_client_key(ref):
    return ref.client_ref_id() if hasattr(ref, 'client_ref_id') else str(ref.pk)


def _bible_cache_id(bible):
    return str(getattr(bible, 'id', '') or getattr(bible, 'bible_id', '') or bible)


def _verse_cache_key(bible, ref):
    return (
        f"verse_text:v1:{_bible_cache_id(bible)}:{ref.book}:"
        f"{ref.begin_chapter}:{ref.begin_verse}:{ref.end_chapter}:{ref.end_verse}"
    )


def _bible_copyright_cache_key(bible):
    return f"bible_copyright:v1:{_bible_cache_id(bible)}"


def _get_or_fetch_verse_text(bible, ref):
    text, _ = _get_or_fetch_verse_text_with_source(bible, ref)
    return text


def _get_or_fetch_verse_text_with_source(bible, ref):
    cache_key = _verse_cache_key(bible, ref)
    cached_copyright = cache.get(_bible_copyright_cache_key(bible))
    if cached_copyright:
        bible.copyright = cached_copyright

    cached = cache.get(cache_key)
    if cached is not None:
        return cached, 'cache'

    ref.set_bible(bible)
    text = ref.text() or ''
    cache.set(cache_key, text, VERSE_CACHE_TIMEOUT)
    if getattr(bible, 'copyright', ''):
        cache.set(_bible_copyright_cache_key(bible), bible.copyright, VERSE_CACHE_TIMEOUT)
    return text, 'api'


def _requested_ref_ids(request):
    requested = []
    requested.extend(request.POST.getlist('verse_refs[]'))
    requested.extend(request.POST.getlist('verse_refs'))

    # Support a single comma-separated value as fallback.
    single = request.POST.get('verse_refs', '')
    if single and ',' in single:
        requested.extend(single.split(','))

    normalized = {str(item).strip() for item in requested if str(item).strip()}
    return normalized


class BibleVersesCommandmentView(View):
    """AJAX endpoint: save new bible preference and return all verse texts for a commandment."""
    def post(self, request, commandment_id: int):
        bible_id = request.POST.get('bible_id', '')
        prefs = UserPreferences(request.session)
        if bible_id:
            if not is_bible_id_visible_for_request(request, bible_id):
                return JsonResponse({'error': 'Bible disabled'}, status=400)
            new_bible = BibleTranslation().get(bible_id)
            prefs.bible = new_bible
        else:
            new_bible = prefs.bible

        commandment = get_object_or_404(Commandment, pk=commandment_id)
        commandment.bible = new_bible

        verses = {}
        verse_sources = {}
        primary = commandment.primary_bible_reference()
        if primary:
            text, source = _get_or_fetch_verse_text_with_source(new_bible, primary)
            primary_key = _reference_client_key(primary)
            verses[primary_key] = text if text else ''
            verse_sources[primary_key] = source

        for method_name in [
            'direct_bible_references',
            'indirect_bible_references',
            'example_bible_references',
            'otlaw_bible_references',
            'wisdom_bible_references',
            'duplicate_bible_references',
            'study_bible_references',
        ]:
            verses.update(
                _collect_verses(
                    new_bible,
                    getattr(commandment, method_name)(),
                    key_builder=_reference_client_key,
                    verse_sources=verse_sources,
                )
            )

        requested_ref_ids = _requested_ref_ids(request)

        if requested_ref_ids:
            verses = {pk: text for pk, text in verses.items() if pk in requested_ref_ids}
            verse_sources = {pk: src for pk, src in verse_sources.items() if pk in requested_ref_ids}

        return JsonResponse({'verses': verses, 'verse_sources': verse_sources})


class BibleVersesLessonView(View):
    """AJAX endpoint: save new bible preference and return all verse texts for a lesson."""
    def post(self, request, lesson_id: int):
        bible_id = request.POST.get('bible_id', '')
        prefs = UserPreferences(request.session)
        if bible_id:
            if not is_bible_id_visible_for_request(request, bible_id):
                return JsonResponse({'error': 'Bible disabled'}, status=400)
            new_bible = BibleTranslation().get(bible_id)
            prefs.bible = new_bible
        else:
            new_bible = prefs.bible

        lesson = get_object_or_404(Lesson, pk=lesson_id)
        lesson.bible = new_bible
        if lesson.commandment:
            lesson.commandment.bible = new_bible

        verses = {}
        verse_sources = {}
        primary = lesson.primary_bible_reference()
        if primary:
            text, source = _get_or_fetch_verse_text_with_source(new_bible, primary)
            primary_key = str(primary.pk)
            verses[primary_key] = text if text else ''
            verse_sources[primary_key] = source

        verses.update(_collect_verses(new_bible, lesson.direct_bible_references(), verse_sources=verse_sources))

        requested_ref_ids = _requested_ref_ids(request)

        if requested_ref_ids:
            verses = {pk: text for pk, text in verses.items() if pk in requested_ref_ids}
            verse_sources = {pk: src for pk, src in verse_sources.items() if pk in requested_ref_ids}

        return JsonResponse({'verses': verses, 'verse_sources': verse_sources})

