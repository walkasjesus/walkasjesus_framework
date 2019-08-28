from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleReferences, UserPreferences


class StudyListingView(View):
    def get(self, request):
        bible_references = BibleReferences()
        bible_references.bible = UserPreferences(request.session).bible
        return render(request, 'commandments/study_listing.html', {'bible_references': bible_references})
