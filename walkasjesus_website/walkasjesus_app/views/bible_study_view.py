import logging

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from walkasjesus_app.lib.access_policy import filter_visible_bibles_for_request, is_bible_id_visible_for_request
from walkasjesus_app.models import BibleTranslation, UserPreferences
from walkasjesus_app.models.bible_books import BibleBooks

logger = logging.getLogger(__name__)

VERSE_CACHE_TIMEOUT = int(getattr(settings, 'BIBLE_API_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))

_OT_BOOKS = {
    'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges', 'Ruth',
    'SamuelFirstBook', 'SamuelSecondBook', 'KingsFirstBook', 'KingsSecondBook',
    'ChroniclesFirstBook', 'ChroniclesSecondBook', 'Ezra', 'Nehemiah', 'Esther', 'Job',
    'Psalms', 'Proverbs', 'Ecclesiastes', 'SongOfSolomon', 'Isaiah', 'Jeremiah',
    'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel', 'Amos', 'Obadiah', 'Jonah',
    'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah', 'Malachi',
}

# Maps app BibleBooks enum names to Sefaria reference names (OT only)
_SEFARIA_BOOK_NAMES = {
    'Genesis': 'Genesis', 'Exodus': 'Exodus', 'Leviticus': 'Leviticus', 'Numbers': 'Numbers',
    'Deuteronomy': 'Deuteronomy', 'Joshua': 'Joshua', 'Judges': 'Judges', 'Ruth': 'Ruth',
    'SamuelFirstBook': 'I Samuel', 'SamuelSecondBook': 'II Samuel',
    'KingsFirstBook': 'I Kings', 'KingsSecondBook': 'II Kings',
    'ChroniclesFirstBook': 'I Chronicles', 'ChroniclesSecondBook': 'II Chronicles',
    'Ezra': 'Ezra', 'Nehemiah': 'Nehemiah', 'Esther': 'Esther', 'Job': 'Job',
    'Psalms': 'Psalms', 'Proverbs': 'Proverbs', 'Ecclesiastes': 'Ecclesiastes',
    'SongOfSolomon': 'Song of Songs', 'Isaiah': 'Isaiah', 'Jeremiah': 'Jeremiah',
    'Lamentations': 'Lamentations', 'Ezekiel': 'Ezekiel', 'Daniel': 'Daniel',
    'Hosea': 'Hosea', 'Joel': 'Joel', 'Amos': 'Amos', 'Obadiah': 'Obadiah',
    'Jonah': 'Jonah', 'Micah': 'Micah', 'Nahum': 'Nahum', 'Habakkuk': 'Habakkuk',
    'Zephaniah': 'Zephaniah', 'Haggai': 'Haggai', 'Zechariah': 'Zechariah', 'Malachi': 'Malachi',
}

# Maps app BibleBooks enum names to Scriptura/BijbelAPI book names
_SCRIPTURA_BOOK_NAMES = {
    'Genesis': 'Genesis', 'Exodus': 'Exodus', 'Leviticus': 'Leviticus', 'Numbers': 'Numbers',
    'Deuteronomy': 'Deuteronomy', 'Joshua': 'Joshua', 'Judges': 'Judges', 'Ruth': 'Ruth',
    'SamuelFirstBook': '1 Samuel', 'SamuelSecondBook': '2 Samuel',
    'KingsFirstBook': '1 Kings', 'KingsSecondBook': '2 Kings',
    'ChroniclesFirstBook': '1 Chronicles', 'ChroniclesSecondBook': '2 Chronicles',
    'Ezra': 'Ezra', 'Nehemiah': 'Nehemiah', 'Esther': 'Esther', 'Job': 'Job',
    'Psalms': 'Psalms', 'Proverbs': 'Proverbs', 'Ecclesiastes': 'Ecclesiastes',
    'SongOfSolomon': 'Song of Solomon', 'Isaiah': 'Isaiah', 'Jeremiah': 'Jeremiah',
    'Lamentations': 'Lamentations', 'Ezekiel': 'Ezekiel', 'Daniel': 'Daniel',
    'Hosea': 'Hosea', 'Joel': 'Joel', 'Amos': 'Amos', 'Obadiah': 'Obadiah',
    'Jonah': 'Jonah', 'Micah': 'Micah', 'Nahum': 'Nahum', 'Habakkuk': 'Habakkuk',
    'Zephaniah': 'Zephaniah', 'Haggai': 'Haggai', 'Zechariah': 'Zechariah', 'Malachi': 'Malachi',
    'Matthew': 'Matthew', 'Mark': 'Mark', 'Luke': 'Luke', 'John': 'John', 'Acts': 'Acts',
    'Romans': 'Romans', 'CorinthiansFirstBook': '1 Corinthians', 'CorinthiansSecondBook': '2 Corinthians',
    'Galatians': 'Galatians', 'Ephesians': 'Ephesians', 'Philippians': 'Philippians',
    'Colossians': 'Colossians', 'ThessaloniansFirstBook': '1 Thessalonians',
    'ThessaloniansSecondBook': '2 Thessalonians', 'TimothyFirstBook': '1 Timothy',
    'TimothySecondBook': '2 Timothy', 'Titus': 'Titus', 'Philemon': 'Philemon',
    'Hebrews': 'Hebrews', 'James': 'James', 'PeterFirstBook': '1 Peter', 'PeterSecondBook': '2 Peter',
    'JohnFirstBook': '1 John', 'JohnSecondBook': '2 John', 'JohnThirdBook': '3 John',
    'Jude': 'Jude', 'Revelation': 'Revelation',
}

_VALID_BOOK_NAMES = {b.name for b in BibleBooks}


def _safe_int(value, default, minimum=1):
    try:
        return max(minimum, int(value))
    except (ValueError, TypeError):
        return default


class BibleStudyView(View):
    def get(self, request):
        max_verses = int(getattr(settings, 'BIBLE_STUDY_MAX_VERSES', 5))
        max_bibles = 4

        bible_books = [(b.name, str(b.value)) for b in BibleBooks]

        all_bibles = BibleTranslation().all_in_supported_languages()
        enabled_bibles = filter_visible_bibles_for_request(request, all_bibles)

        book = request.GET.get('book', 'John')
        if book not in _VALID_BOOK_NAMES:
            book = 'John'

        chapter = _safe_int(request.GET.get('chapter'), 3)
        start_verse = _safe_int(request.GET.get('start_verse'), 16)
        end_verse = _safe_int(request.GET.get('end_verse'), start_verse)
        end_verse = max(start_verse, end_verse)
        end_verse = min(end_verse, start_verse + max_verses - 1)

        bible_ids = request.GET.getlist('bible_id')
        if not bible_ids:
            default_bible = UserPreferences(request.session).bible
            bible_ids = [default_bible.id] if default_bible else []
        bible_ids = [str(bid).strip() for bid in bible_ids if str(bid).strip()][:max_bibles]

        visible_ids = {b.id for b in enabled_bibles}
        bible_ids = [bid for bid in bible_ids if bid in visible_ids]
        if not bible_ids and enabled_bibles:
            bible_ids = [enabled_bibles[0].id]

        verse_range = list(range(start_verse, end_verse + 1))
        is_ot_book = book in _OT_BOOKS
        sefaria_book = _SEFARIA_BOOK_NAMES.get(book, book)
        scriptura_book = _SCRIPTURA_BOOK_NAMES.get(book, book)

        verse_data = []
        verse_texts_by_bible = {}
        for v in verse_range:
            verse_data.append({
                'verse_num': v,
                'sefaria_ref': f'{sefaria_book} {chapter}:{v}' if is_ot_book else '',
                'scriptura_book': scriptura_book,
                'scriptura_chapter': chapter,
                'scriptura_verse': v,
                'is_ot': is_ot_book,
            })

        bt = BibleTranslation()
        selected_bibles = []
        for bid in bible_ids:
            bible_obj = bt.get(bid)
            if bible_obj:
                bible_book = BibleLibBibleBooks[book]
                verse_texts = {}
                verse_sources = {}
                for v in verse_range:
                    cache_key = f'bible_study:v1:{bid}:{book}:{chapter}:{v}'
                    cached = None if getattr(settings, 'DISABLE_CACHE_FOR_DEBUG', False) else cache.get(cache_key)
                    if cached is not None:
                        verse_texts[str(v)] = cached
                        verse_sources[str(v)] = 'cache'
                        continue
                    try:
                        text = bible_obj.verses(bible_book, chapter, v, chapter, v)
                    except Exception:
                        logger.exception('Failed to load verse text for bible=%s book=%s chapter=%s verse=%s', bid, book, chapter, v)
                        text = ''
                    verse_texts[str(v)] = text or ''
                    verse_sources[str(v)] = 'api'
                    if text:
                        cache.set(cache_key, text, VERSE_CACHE_TIMEOUT)
                verse_texts_by_bible[bid] = verse_texts
                selected_bibles.append({
                    'id': bid,
                    'name': bible_obj.name,
                    'language_code': str(getattr(bible_obj, 'language', '') or '').strip().upper()[:2],
                    'display_name': f"{str(getattr(bible_obj, 'language', '') or '').strip().upper()[:2]} - {bible_obj.name}" if str(getattr(bible_obj, 'language', '') or '').strip() else bible_obj.name,
                    'verse_texts': verse_texts,
                    'verse_sources': verse_sources,
                    'copyright': getattr(bible_obj, 'copyright', ''),
                })

        book_label = str(BibleBooks[book].value) if book in _VALID_BOOK_NAMES else book
        visible_bible_slots = max(1, min(max_bibles, len(selected_bibles) or 1))

        return render(request, 'bible_study/bible_study.html', {
            'bible_books': bible_books,
            'enabled_bibles': enabled_bibles,
            'selected_book': book,
            'selected_book_label': book_label,
            'selected_chapter': chapter,
            'selected_start_verse': start_verse,
            'selected_end_verse': end_verse,
            'selected_bible_ids': bible_ids,
            'selected_bibles': selected_bibles,
            'verse_data': verse_data,
            'max_verses': max_verses,
            'max_bibles': max_bibles,
            'visible_bible_slots': visible_bible_slots,
            'is_ot_book': is_ot_book,
        })


class BibleStudyVersesView(View):
    """AJAX endpoint: returns verse texts for a given bible + book/chapter/verse range."""

    def post(self, request):
        bible_id = str(request.POST.get('bible_id', '')).strip()
        book_name = str(request.POST.get('book', '')).strip()
        chapter = _safe_int(request.POST.get('chapter'), 1)
        start_verse = _safe_int(request.POST.get('start_verse'), 1)
        end_verse = _safe_int(request.POST.get('end_verse'), start_verse)
        end_verse = max(start_verse, end_verse)

        max_verses = int(getattr(settings, 'BIBLE_STUDY_MAX_VERSES', 5))
        end_verse = min(end_verse, start_verse + max_verses - 1)

        if book_name not in _VALID_BOOK_NAMES:
            return JsonResponse({'error': 'Invalid book'}, status=400)

        if not is_bible_id_visible_for_request(request, bible_id):
            return JsonResponse({'error': 'Bible not available'}, status=403)

        bt = BibleTranslation()
        bible = bt.get(bible_id)
        if not bible:
            return JsonResponse({'error': 'Bible not found'}, status=404)

        bible_lib_book = BibleLibBibleBooks[book_name]
        disable_cache = getattr(settings, 'DISABLE_CACHE_FOR_DEBUG', False)
        verses = {}
        verse_sources = {}
        for v in range(start_verse, end_verse + 1):
            cache_key = f'bible_study:v1:{bible_id}:{book_name}:{chapter}:{v}'
            cached = None if disable_cache else cache.get(cache_key)
            if cached is not None:
                verses[str(v)] = cached
                verse_sources[str(v)] = 'cache'
                continue
            try:
                text = bible.verses(bible_lib_book, chapter, v, chapter, v)
            except Exception:
                text = ''
            verses[str(v)] = text or ''
            verse_sources[str(v)] = 'api'
            if text:
                cache.set(cache_key, text, VERSE_CACHE_TIMEOUT)

        language_code = str(getattr(bible, 'language', '') or '').strip().upper()[:2]
        display_name = f'{language_code} - {getattr(bible, "name", bible_id)}' if language_code else getattr(bible, 'name', bible_id)
        return JsonResponse({
            'verses': verses,
            'verse_sources': verse_sources,
            'bible_name': getattr(bible, 'name', bible_id),
            'bible_display_name': display_name,
            'copyright': getattr(bible, 'copyright', ''),
        })
