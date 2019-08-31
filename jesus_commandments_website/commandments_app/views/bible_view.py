from gettext import gettext

from bible_lib import BibleFactory
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views import View

from commandments_app.models import UserPreferences


class BibleView(View):
    def post(self, request):
        if 'bible_id' in request.POST:
            new_bible = BibleFactory().create(request.POST['bible_id'])
            UserPreferences(request.session).bible = new_bible
        else:
            messages.error(request, gettext('Failed to change the bible translation'))

        return HttpResponseRedirect(request.POST.get('next', '/'))
