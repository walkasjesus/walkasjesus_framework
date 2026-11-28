"""Chapter boundaries shared by the prefetch command and cache reporting."""

from functools import lru_cache

from walkasjesus_app.lib.strongs_service import _hebrew_verse_index
from walkasjesus_app.views.bible_study_view import (
    _CANONICAL_CHAPTER_COUNTS,
    _OT_BOOKS,
    _chapter_max_verse_for_bible,
)


@lru_cache(maxsize=None)
def _hebrew_chapter_maxima(book_name):
    maxima = {}
    for chapter, verse in _hebrew_verse_index(book_name)[0]:
        maxima[chapter] = max(maxima.get(chapter, 0), verse)
    return maxima


def chapters_for_book(book_name):
    if book_name in _OT_BOOKS:
        hebrew_chapters = sorted(_hebrew_chapter_maxima(book_name))
        if hebrew_chapters:
            return hebrew_chapters
    return range(1, _CANONICAL_CHAPTER_COUNTS.get(book_name, 0) + 1)


def max_display_verse(bible, book_name, chapter):
    if book_name in _OT_BOOKS:
        return _hebrew_chapter_maxima(book_name).get(chapter, 0)
    return _chapter_max_verse_for_bible(bible, book_name, chapter)
