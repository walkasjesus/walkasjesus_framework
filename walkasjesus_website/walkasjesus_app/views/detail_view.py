from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views import View

from walkasjesus_app.models import Commandment, UserPreferences, Lesson, BibleTranslation


class DetailView(View):
    def get(self, request, commandment_id: int):
        commandment = get_object_or_404(Commandment, pk=commandment_id)
        selected_bible = UserPreferences(request.session).bible
        commandment.bible = selected_bible
        commandment.languages = UserPreferences(request.session).languages
        return render(request, 'commandments/detail.html', {'commandment': commandment,
                                                            'bible': selected_bible})


class DetailLessonView(View):
    def get(self, request, lesson_id: int):
        lesson = get_object_or_404(Lesson, pk=lesson_id)
        selected_bible = UserPreferences(request.session).bible
        lesson.bible = selected_bible
        lesson.languages = UserPreferences(request.session).languages
        return render(request, 'lessons/detail.html', {'lesson': lesson,
                                                            'bible': selected_bible})


def _collect_verses(bible, references):
    """Fetch verse texts for a list of references using the given bible."""
    verses = {}
    for ref in references:
        ref.set_bible(bible)
        text = ref.text()
        verses[str(ref.pk)] = text if text else ''
    return verses


class BibleVersesCommandmentView(View):
    """AJAX endpoint: save new bible preference and return all verse texts for a commandment."""
    def post(self, request, commandment_id: int):
        bible_id = request.POST.get('bible_id', '')
        prefs = UserPreferences(request.session)
        if bible_id:
            if bible_id in settings.DISABLED_BIBLE_TRANSLATIONS:
                return JsonResponse({'error': 'Bible disabled'}, status=400)
            new_bible = BibleTranslation().get(bible_id)
            prefs.bible = new_bible
        else:
            new_bible = prefs.bible

        commandment = get_object_or_404(Commandment, pk=commandment_id)
        commandment.bible = new_bible

        verses = {}
        primary = commandment.primary_bible_reference()
        if primary:
            primary.set_bible(new_bible)
            text = primary.text()
            verses[str(primary.pk)] = text if text else ''

        for method_name in [
            'direct_bible_references',
            'indirect_bible_references',
            'example_bible_references',
            'otlaw_bible_references',
            'wisdom_bible_references',
        ]:
            verses.update(_collect_verses(new_bible, getattr(commandment, method_name)()))

        return JsonResponse({'verses': verses})


class BibleVersesLessonView(View):
    """AJAX endpoint: save new bible preference and return all verse texts for a lesson."""
    def post(self, request, lesson_id: int):
        bible_id = request.POST.get('bible_id', '')
        prefs = UserPreferences(request.session)
        if bible_id:
            if bible_id in settings.DISABLED_BIBLE_TRANSLATIONS:
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
        primary = lesson.primary_bible_reference()
        if primary:
            primary.set_bible(new_bible)
            text = primary.text()
            verses[str(primary.pk)] = text if text else ''

        verses.update(_collect_verses(new_bible, lesson.direct_bible_references()))

        return JsonResponse({'verses': verses})

