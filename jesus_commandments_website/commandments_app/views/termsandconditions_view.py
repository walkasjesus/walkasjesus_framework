from django.shortcuts import render
from django.views import View


class TermsView(View):
    def get(self, request):
        return render(request, 'commandments/termsandconditions.html', {})
