from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleReference, UserPreferences
from bible_lib.bible_books import BibleBooks


class LegalismView(View):
    def get(self, request):

        selected_bible = UserPreferences(request.session).bible
        
        mat_5_17_20 = BibleReference(selected_bible, BibleBooks.Matthew, 5, 17, 5, 20)
        joh_15_10 = BibleReference(selected_bible, BibleBooks.John, 15, 10, 15, 10)

        return render(request, 'commandments/legalism.html', {'mat_5_17_20': mat_5_17_20,
                                                            'joh_15_10': joh_15_10,
                                                            'bible': selected_bible})

