from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment, Lesson


class ListingView(View):
    def get(self, request):
        commandments_ordered = Commandment.objects.order_by('id').all().prefetch_related('drawing_set')
        return render(request, 'commandments/listing.html', {'commandments': commandments_ordered})

class ListingLessonView(View):
    def get(self, request):
        lessons_ordered = Lesson.objects.order_by('id').all().prefetch_related('drawing_set')
        return render(request, 'lessons/listing.html', {'lessons': lessons_ordered})
