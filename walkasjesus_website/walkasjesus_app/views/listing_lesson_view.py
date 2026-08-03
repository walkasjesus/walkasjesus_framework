from django.shortcuts import render
from django.utils import translation
from django.views import View

from walkasjesus_app.models import Lesson
from walkasjesus_app.media_image_utils import media_file_exists


def _first_public(items):
    return next((item for item in items if item.is_public), '')


def _first_public_existing_image(items):
    return next((item for item in items if item.is_public and item.img_url and media_file_exists(item.img_url)), '')


def _first_language_public(items, languages):
    return next((item for item in items if item.is_public and item.language in languages), '')


def _first_public_kids_or_any(items):
    return next((item for item in items if item.is_public and item.target_audience in {'any', 'kids'}), '')


def _lesson_card_drawing(lesson):
    lesson_drawings = list(lesson.lessondrawing_set.all())
    drawing = _first_public_existing_image(lesson_drawings)
    if drawing:
        return drawing

    shared_drawings = [
        item for item in lesson.shared_media_resources.all()
        if item.media_type == 'drawing' and item.is_public
    ]
    drawing = _first_public_existing_image(shared_drawings)
    if drawing:
        return drawing

    if lesson.commandment:
        commandment_drawings = list(lesson.commandment.drawing_set.all())
        drawing = _first_public_existing_image(commandment_drawings)
        if drawing:
            return drawing

        commandment_shared_drawings = [
            item for item in lesson.commandment.shared_media_resources.all()
            if item.media_type == 'drawing' and item.is_public
        ]
        drawing = _first_public_existing_image(commandment_shared_drawings)
        if drawing:
            return drawing

    return _first_public(lesson_drawings) or (shared_drawings[0] if shared_drawings else '')


def _prepare_lesson_card(lesson):
    languages = {'any', translation.get_language()}
    lesson.card_background_drawing = _lesson_card_drawing(lesson)
    lesson.card_background_thumbnail_url = lesson.card_background_drawing.thumbnail_url() if lesson.card_background_drawing else ''
    lesson.card_has_superbook = bool(_first_public(lesson.lessonsuperbook_set.all()))
    lesson.card_has_henkieshow = bool(_first_language_public(lesson.lessonhenkieshow_set.all(), languages))
    lesson.card_has_song = bool(_first_language_public(lesson.lessonsong_set.all(), languages))
    lesson.card_has_short_movie = bool(_first_language_public(lesson.lessonshortmovie_set.all(), languages))
    lesson.card_has_testimony = bool(_first_language_public(lesson.lessontestimony_set.all(), languages))
    if lesson.commandment:
        lesson.card_has_henkieshow = lesson.card_has_henkieshow or bool(_first_language_public(lesson.commandment.henkieshow_set.all(), languages))
        lesson.card_has_song = lesson.card_has_song or bool(_first_public_kids_or_any(lesson.commandment.song_set.all()))
        lesson.card_has_short_movie = lesson.card_has_short_movie or bool(_first_public_kids_or_any(lesson.commandment.shortmovie_set.all()))
        lesson.card_has_testimony = lesson.card_has_testimony or bool(_first_public_kids_or_any(lesson.commandment.testimony_set.all()))
    lesson.card_bible_sections = sorted(lesson.lesson_bible_section.all())
    return lesson


class ListingLessonView(View):
    def get(self, request):
        lessons_ordered = list(
            Lesson.objects
            .select_related('commandment')
            .order_by('id')
            .prefetch_related(
                'lesson_bible_section',
                'lessondrawing_set',
                'lessonsuperbook_set',
                'lessonhenkieshow_set',
                'lessonsong_set',
                'lessonshortmovie_set',
                'lessontestimony_set',
                'shared_media_resources',
                'commandment__drawing_set',
                'commandment__henkieshow_set',
                'commandment__song_set',
                'commandment__shortmovie_set',
                'commandment__testimony_set',
                'commandment__shared_media_resources',
            )
        )
        for lesson in lessons_ordered:
            _prepare_lesson_card(lesson)
        return render(request, 'lessons/lesson_listing.html', {'lessons': lessons_ordered})
