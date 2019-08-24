from bible_lib import BibleFactory
from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleReferences


class StudyListingView(View):
    def get(self, request, bible_id: str):
        bible_references = BibleReferences()
        bible_references.bible = BibleFactory().create(bible_id)
        return render(request, 'commandments/study_listing.html', {'bible_references': bible_references})
