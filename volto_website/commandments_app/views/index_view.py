from bible_lib import Bibles
from django.conf import settings
from django.shortcuts import render
from django.utils.functional import cached_property
from django.views import View

from django.contrib.auth.models import User
from commandments_app.models import Commandment


class IndexView(View):
    def get(self, request):
        languages_total = len(settings.LANGUAGES)
        commandments_total = Commandment.objects.count()
        users_total = User.objects.count()
        bibles_total = self._bibles_total

        commandments_with_background_drawing = [c for c in Commandment.objects.all() if c.background_drawing()]

        return render(request, 'commandments/index.html', {'commandments': commandments_with_background_drawing,
                                                           'languages_total': languages_total,
                                                           'bibles_total': bibles_total,
                                                           'commandments_total': commandments_total,
                                                           'users_total': users_total})

    @cached_property
    def _bibles_total(self):
        count = 0
        bibles = Bibles().list()
        languages = [code for code, name in settings.LANGUAGES]

        for bible in bibles:
            if bible.language in languages:
                count += 1

        return count


