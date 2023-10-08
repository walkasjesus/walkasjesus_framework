from django.shortcuts import render
from django.views import View

from commandments_app.models import Lesson, LessonDrawing


class ListingLessonView(View):
    def get(self, request):
        lessons_ordered = Lesson.objects.order_by('id').all()
        drawings_by_lesson = LessonDrawing.objects.filter(lesson__in=lessons_ordered)
        return render(request, 'lessons/lesson_listing.html', {'lessons': lessons_ordered, 'drawings_by_lesson': drawings_by_lesson})
