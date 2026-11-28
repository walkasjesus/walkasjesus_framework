import json
import logging
import re
import time

from bible_lib import BibleBooks
from bible_lib.bible_api.api_bible import ApiBible
from bible_lib.bible_api.services import Services
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.urls import reverse
from django.views import View

from walkasjesus_app.lib.bible_chapter_prefetch import chapters_for_book, max_display_verse
from walkasjesus_app.lib.bible_display_limits import max_verses_for_bible_id
from walkasjesus_app.models import BibleTranslation
from walkasjesus_app.models.bibles import BibleTranslationMetaData
from walkasjesus_app.views.bible_study_view import (
    _CANONICAL_CHAPTER_COUNTS,
    _study_numbering_profile,
    _study_verse_references,
)
from walkasjesus_app.models.bible_numbering import BibleNumberingReview

logger = logging.getLogger(__name__)
_CHAPTER_KEY = re.compile(
    r'/bibles/([^/]+)/passages/([A-Z0-9]+)\.(\d+)\.1-\2\.\3\.\d+'
    r'\?content-type=text&include-titles=false$'
)


class AdminBibleView(View):
    @method_decorator(staff_member_required)
    def get(self, request):
        supported_language_codes = {
            str(code).strip().lower() for code, _ in getattr(settings, 'LANGUAGES', [])
            if str(code).strip()
        }
        bibles = [
            bible for bible in BibleTranslation().all()
            if str(getattr(bible, 'language', '') or '').strip().lower() in supported_language_codes
        ]
        cache = Services().cache
        try:
            with cache.cache_path.open(encoding='utf-8') as file:
                cached_entries = json.load(file)
            if not isinstance(cached_entries, dict):
                raise ValueError('Bible API cache must be a JSON object')
        except FileNotFoundError:
            cached_entries = {}
        except (OSError, ValueError) as error:
            logger.warning('Could not read Bible API cache for chapter reporting: %s', error)
            cached_entries = None

        cached_books = {}
        if cached_entries is not None:
            for key in cached_entries:
                match = _CHAPTER_KEY.search(key)
                if match:
                    cached_books.setdefault(match[1], {}).setdefault(match[2], []).append(
                        (int(match[3]), cached_entries[key]))
        chapter_counts = {book: chapters_for_book(book) for book in _CANONICAL_CHAPTER_COUNTS}
        total_chapters = sum(len(chapters) for chapters in chapter_counts.values())
        numbering_profiles = {
            'sv': _('KJV storage references; embedded Dutch references. Psalm titles are separated.'),
            'hsv': _('Uses SV references outside Psalms (not independently verified); Hebrew numbering in Psalms.'),
            'kjv': _('KJV reference profile; Hebrew references are converted using STEPBible.'),
            'naardense': _('Hebrew numbering in Psalms, Hosea and Joel; other numbering differences are not verified.'),
            'cjb': _('Hebrew numbering in Hosea; other numbering differences are not verified.'),
            'unknown': _('Verse numbering for this translation has not been verified.'),
        }
        reviews = {
            review.bible_id: review
            for review in BibleNumberingReview.objects.all()
        }

        for bible in bibles:
            bible.numbering_status = numbering_profiles[_study_numbering_profile(bible)]
            review = reviews.get(bible.id)
            bible.numbering_review_status = review.scanned_at if review else _('No scan yet')
            bible.numbering_review_url = (
                reverse('admin:commandments_app_biblenumberingreview_change', args=[review.pk])
                if review else ''
            )
            bible.cached_chapters = None
            bible.total_chapters = total_chapters
            bible.percentage_cached = None
            if (cached_entries is not None and isinstance(bible, ApiBible)
                    and not max_verses_for_bible_id(bible.id)):
                bible.cached_chapters = self.bible_count_in_cache(
                    bible, cached_books.get(bible.id, {}), chapter_counts)
                bible.percentage_cached = bible.cached_chapters / total_chapters * 100 if total_chapters else 0

            # Because the translation are retrieved from a library, new one can appear dynamically.
            if not BibleTranslationMetaData.objects.filter(bible_id=bible.id).exists():
                meta_data = BibleTranslationMetaData()
                meta_data.bible_id = bible.id
                # Newly discovered translations are enabled by default; supported-language
                # filtering happens at the view / queryset level, not by mutating DB state.
                meta_data.is_enabled = True
                meta_data.save()
            else:
                meta_data = BibleTranslationMetaData.objects.get(bible_id=bible.id)

            bible.enabled = meta_data.is_enabled and str(bible.id).strip() not in {
                str(item).strip() for item in getattr(settings, 'DISABLED_BIBLE_TRANSLATIONS', []) if str(item).strip()
            }

        bibles.sort(key=lambda b: (b.enabled, b.percentage_cached if b.percentage_cached is not None else -1),
                    reverse=True)

        return render(request, 'admin/bible_admin.html', {'bibles': bibles,
                                                          'cache_items_not_persisted': cache.cache_items_not_persisted,
                                                          'chapter_cache_unavailable': cached_entries is None})

    def bible_count_in_cache(self, bible, cached_books, chapter_counts):
        cached_count = 0
        now = time.time()
        for book_name, chapters in chapter_counts.items():
            book = BibleBooks[book_name]
            passages = cached_books.get(bible.query_builder._get_book_id(bible.id, book), [])
            if not passages:
                continue
            available = {}
            for source_chapter, entry in passages:
                available.setdefault(source_chapter, set()).update(
                    self.cached_passage_verses(bible, book, source_chapter, entry, now))
            for chapter in chapters:
                last_verse = max_display_verse(bible, book_name, chapter)
                if not last_verse:
                    continue
                has_mapped_verses = False
                for verse in range(1, last_verse + 1):
                    sources = _study_verse_references(bible, book_name, chapter, verse, 'hebrew')[0]
                    if not sources:
                        continue
                    has_mapped_verses = True
                    if any(source_verse not in available.get(source_chapter, set())
                           for source_chapter, source_verse in sources):
                        break
                else:
                    if has_mapped_verses:
                        cached_count += 1
        return cached_count

    @staticmethod
    def cached_passage_verses(bible, book, chapter, entry, now):
        if not entry:
            return set()
        if isinstance(entry, dict) and 'value' in entry:
            expires_at = entry.get('expires_at')
            if expires_at is not None:
                try:
                    if float(expires_at) <= now:
                        return set()
                except (TypeError, ValueError):
                    return set()
            entry = entry['value']
        try:
            content = json.loads(entry)['data']['content']
            verses = bible.extract_verses(book, chapter, content)
        except (TypeError, ValueError, KeyError):
            return set()
        return {number for verse in verses if verse.chapter == chapter and verse.text
                for number in range(verse.verse, verse.end_verse + 1)}
