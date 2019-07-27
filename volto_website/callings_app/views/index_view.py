from django.shortcuts import render
from django.views import View

from callings_app.models import Calling


class IndexView(View):
    def get(self, request):
        callings = Calling.objects.order_by('quote')[0:20]
        return render(request, 'callings/index.html', {'callings': callings})
