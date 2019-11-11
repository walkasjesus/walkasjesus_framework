from bible_lib import BibleBooks
from bible_lib.bible_api.cache_controller import CacheController
from bible_lib.bible_api.services import Services
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from commandments_app.models import BibleTranslation, BibleReferences
from commandments_app.models.bibles import BibleTranslationMetaData
from jesus_commandments_website import settings


class AdminBibleView(View):
    @method_decorator(staff_member_required)
    def get(self, request):
        bibles = BibleTranslation().all()
        cache = Services().cache
        cache_controller = CacheController(cache)

        for bible in bibles:
            if bible.id == 'hsv':
                cached_count = 1
                total_count = 1
            else:
                cached_count, total_count = self.bible_count_in_cache(bible, cache_controller)

            bible.percentage_cached = cached_count / max(total_count, 0.0001) * 100

            # Because the translation are retrieved from a library, new one can appear dynamically.
            if not BibleTranslationMetaData.objects.filter(bible_id=bible.id).exists():
                meta_data = BibleTranslationMetaData()
                meta_data.bible_id = bible.id
                # Default enable only in supported languages
                languages = [code for code, name in settings.LANGUAGES]
                meta_data.is_enabled = bible.language in languages
                meta_data.save()
            else:
                meta_data = BibleTranslationMetaData.objects.get(bible_id=bible.id)

            bible.enabled = meta_data.is_enabled

        bibles.sort(key=lambda b: (b.enabled, b.percentage_cached), reverse=True)

        return render(request, 'admin/bible_admin.html', {'bibles': bibles,
                                                          'cache_items_not_persisted': cache.cache_items_not_persisted})

    def bible_count_in_cache(self, bible, cache_controller):
        bible_references = BibleReferences()
        bible_references.bible = bible
        cached_count_1, total_count_1 = self.count_in_cache(cache_controller, bible_references.primary())
        cached_count_2, total_count_2 = self.count_in_cache(cache_controller, bible_references.secondary())
        cached_count_3, total_count_3 = self.count_in_cache(cache_controller, bible_references.tertiary())
        cached_count = cached_count_1 + cached_count_2 + cached_count_3
        total_count = total_count_1 + total_count_2 + total_count_3
        return cached_count, total_count

    def count_in_cache(self, cache_controller, references):
        cached_count = 0
        total_count = 0
        for ref in references:
            total_count += 1
            if self.is_verse_in_cache(cache_controller, ref):
                cached_count += 1
        return cached_count, total_count

    def is_verse_in_cache(self, cache_controller, ref):
        if ref.end_chapter == 0:
            end_chapter = ref.begin_chapter
        else:
            end_chapter = ref.end_chapter
        if ref.end_verse == 0:
            end_verse = ref.begin_verse
        else:
            end_verse = ref.end_verse
        return cache_controller.contains_verses(ref.bible.id,
                                                BibleBooks[ref.book],
                                                ref.begin_chapter,
                                                ref.begin_verse,
                                                end_chapter,
                                                end_verse)
