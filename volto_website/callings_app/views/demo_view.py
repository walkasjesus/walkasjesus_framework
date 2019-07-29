from django.shortcuts import render
from django.views import View

from callings_app.models import Calling


class DemoView(View):
    def get(self, request):
        return render(request, 'callings/demo.html')
