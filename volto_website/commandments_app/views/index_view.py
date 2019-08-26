from django.conf import settings
from django.shortcuts import render
from django.views import View

from django.contrib.auth.models import User
from commandments_app.models import Commandment


class IndexView(View):
    def get(self, request):
        languages_total = len(settings.LANGUAGES)
        commandments_total = Commandment.objects.count()
        users_total = User.objects.count()

        commandments_with_background_drawing = [c for c in Commandment.objects.all() if c.background_drawing()]

        return render(request, 'commandments/index.html', {'commandments': commandments_with_background_drawing,
                                                           'languages_total': languages_total,
                                                           'commandments_total': commandments_total,
                                                           'users_total': users_total})



