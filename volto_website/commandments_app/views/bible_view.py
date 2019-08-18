from gettext import gettext

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views import View

from commandments_app.models import UserPreferences


class BibleView(View):
    def post(self, request):
        if 'bible_id' in request.POST:
            UserPreferences(request.session).set_bible_id(request.POST['bible_id'])
        else:
            messages.error(request, gettext('Failed to change the bible translation'))

        return HttpResponseRedirect(request.POST.get('next', '/'))
