from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment


class IndexView(View):
    def get(self, request):
        commandments = Commandment.objects.order_by('quote')[0:20]
        return render(request, 'commandments/index.html', {'commandments': commandments})
