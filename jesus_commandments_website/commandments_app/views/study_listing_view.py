from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleReferences, UserPreferences


class StudyListingView(View):
    def get(self, request):
        bible_references = BibleReferences()
        selected_bible = UserPreferences(request.session).bible
        bible_references.bible = selected_bible
        return render(request, 'commandments/study_listing.html', {'bible_references': bible_references,
                                                                   'bible': selected_bible})
