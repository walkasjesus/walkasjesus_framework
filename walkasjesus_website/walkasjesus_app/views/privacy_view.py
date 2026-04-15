from django.shortcuts import render
from django.views import View


class PrivacyView(View):
    def get(self, request):
        return render(request, 'commandments/privacy.html', {})
