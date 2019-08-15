from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment
from django.conf import settings

class IndexView(View):
    def get(self, request):
        commandments_all = Commandment.objects.order_by('title')
        commandments_total = len(commandments_all)
        languages_all = settings.LANGUAGES
        languages_total = len(languages_all)
        commandments = Commandment.objects.order_by('title')[0:20]

        return render(request, 'commandments/index.html', {'commandments': commandments,
                                                           'languages_all': languages_all,
                                                           'languages_total': languages_total,
                                                           'commandments_total': commandments_total})