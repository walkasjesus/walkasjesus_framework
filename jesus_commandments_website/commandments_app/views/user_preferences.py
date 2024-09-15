from gettext import gettext
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.views import View
from django.conf import settings
from commandments_app.models import UserPreferences, BibleTranslation

class UserPreferencesBibleView(View):
    def post(self, request):
        bible_id = request.POST.get('bible_id')
        if bible_id:
            try:
                new_bible = BibleTranslation().get(bible_id)
                
                # Check if the selected Bible is in the disabled list
                if bible_id in settings.DISABLED_BIBLE_TRANSLATIONS:
                    messages.error(request, gettext('The selected Bible translation is currently disabled.'))
                else:
                    UserPreferences(request.session).bible = new_bible
                    messages.success(request, gettext('Bible translation changed successfully.'))
            except BibleTranslation.DoesNotExist:
                messages.error(request, gettext('Bible translation not found.'))
        else:
            messages.error(request, gettext('Failed to change the Bible translation.'))

        return HttpResponseRedirect(request.POST.get('next', '/'))


class UserPreferencesLanguagesView(View):
    def post(self, request):
        redirect = HttpResponseRedirect(request.POST.get('next', '/'))

        if 'languages' not in request.POST:
            messages.error(request, gettext('Failed to change the user languages'))
            return redirect

        selected_languages = request.POST.getlist('languages')

        if selected_languages:
            UserPreferences(request.session).languages = selected_languages
            messages.success(request, gettext('Languages updated successfully.'))
        else:
            messages.error(request, gettext('No languages selected'))

        return redirect

