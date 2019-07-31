from django.shortcuts import render
from django.views import View


class DemoView(View):
    def get(self, request):
        return render(request, 'commandments/demo.html')
