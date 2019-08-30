from django.conf import settings
from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleTranslation


class BibleAdminView(View):
    def get(self, request):
        if not settings.DEBUG:
            raise Exception('Not implemented login for this page')

        bibles = BibleTranslation().all_in_supported_languages()
        return render(request, 'admin/bible_admin.html', {'bibles': bibles})
