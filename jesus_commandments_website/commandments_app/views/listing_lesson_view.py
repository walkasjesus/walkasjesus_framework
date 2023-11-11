from django.shortcuts import render
from django.views import View

from commandments_app.models import Lesson


class ListingLessonView(View):
    def get(self, request):
        lessons_ordered = Lesson.objects.order_by('id').all().prefetch_related('lessondrawing_set')
        return render(request, 'lessons/lesson_listing.html', {'lessons': lessons_ordered})
