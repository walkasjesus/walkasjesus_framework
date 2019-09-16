from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment, BibleTranslation


class IndexView(View):
    def get(self, request):
        languages_total = len(settings.LANGUAGES)
        commandments_total = Commandment.objects.count()
        users_total = User.objects.count()
        bibles_total = len(BibleTranslation().all_in_supported_languages())

        return render(request, 'commandments/index.html', {'commandments': Commandment.objects.with_background(),
                                                           'languages_total': languages_total,
                                                           'bibles_total': bibles_total,
                                                           'commandments_total': commandments_total,
                                                           'users_total': users_total})
