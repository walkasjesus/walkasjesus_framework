from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import render
from django.views import View

from walkasjesus_app.models import Commandment, BibleTranslation
from walkasjesus_app.views.detail_view import _allowed_media_languages, _allowed_target_audiences


class IndexView(View):
    def get(self, request):
        commandments = list(Commandment.objects.with_background())
        allowed_target_audiences = _allowed_target_audiences(request)
        allowed_media_languages = _allowed_media_languages(request)
        for commandment in commandments:
            commandment.media_type_badge_list = commandment.media_type_badges(allowed_target_audiences, allowed_media_languages)
        return render(request, 'commandments/index.html', {'commandments': commandments,
                                                           'bibles': BibleTranslation(),
                                                           'languages_total': len(settings.LANGUAGES),
                                                           'commandments_total': Commandment.objects.count(),
                                                           'users_total': User.objects.count()})
