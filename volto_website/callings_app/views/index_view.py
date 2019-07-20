from django.shortcuts import render
from django.views import View

from callings_app.models import Calling


class IndexView(View):
    def get(self, request):
        calling_list = Calling.objects.order_by('quote')[0:20]
        return render(request, 'callings/index.html', {'calling_list': calling_list})
