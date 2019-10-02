from gettext import gettext

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views import View

from commandments_app.models import UserPreferences, Bibles


class UserPreferencesBibleView(View):
    def post(self, request):
        if 'bible_id' in request.POST:
            new_bible = Bibles().get(request.POST['bible_id'])
            UserPreferences(request.session).bible = new_bible
        else:
            messages.error(request, gettext('Failed to change the bible translation'))

        return HttpResponseRedirect(request.POST.get('next', '/'))


class UserPreferencesLanguagesView(View):
    def post(self, request):
        redirect = HttpResponseRedirect(request.POST.get('next', '/'))

        if 'languages' not in request.POST:
            messages.error(request, gettext('Failed to change the user languages'))
            return redirect

        selected_languages = request.POST.getlist('languages')

        if len(selected_languages) >= 1:
            UserPreferences(request.session).languages = selected_languages
        else:
            messages.error(request, gettext('No languages selected'))

        return redirect
