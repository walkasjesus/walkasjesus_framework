from django.conf import settings
from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment


class IndexView(View):
    def get(self, request):
        languages_total = len(settings.LANGUAGES)
        commandments = Commandment.objects.order_by('title')[0:100]
        commandments_total = Commandment.objects.count()

        return render(request, 'commandments/index.html', {'commandments': commandments,
                                                           'languages_total': languages_total,
                                                           'commandments_total': commandments_total})
