from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment, BibleTranslation


class IndexView(View):
    def get(self, request):
        return render(request, 'commandments/index.html', {'commandments': Commandment.objects.with_background(),
                                                           'bibles': BibleTranslation(),
                                                           'languages_total': len(settings.LANGUAGES),
                                                           'commandments_total': Commandment.objects.count(),
                                                           'users_total': User.objects.count()})
