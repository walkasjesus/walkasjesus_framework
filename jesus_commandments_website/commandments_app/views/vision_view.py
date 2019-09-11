from django.shortcuts import render
from django.views import View


class VisionView(View):
    def get(self, request):
        return render(request, 'commandments/vision.html', {})
