from django.shortcuts import render, get_object_or_404
from django.views import View

from commandments_app.models import Commandment, UserPreferences, Lesson


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

