from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleReference, UserPreferences
from bible_lib.bible_books import BibleBooks


class VisionView(View):
    def get(self, request):

        selected_bible = UserPreferences(request.session).bible
        
        johnfirstbook_2_6 = BibleReference(selected_bible, BibleBooks.JohnFirstBook, 2, 6, 2, 6)
        johnfirstbook_2_3_6 = BibleReference(selected_bible, BibleBooks.JohnFirstBook, 2, 3, 2, 6)
        joh_15_10 = BibleReference(selected_bible, BibleBooks.John, 15, 10, 15, 10)
        heb_13_20_21 = BibleReference(selected_bible, BibleBooks.Hebrews, 13, 20, 13, 21)

        return render(request, 'commandments/vision.html', {'johnfirstbook_2_6': johnfirstbook_2_6,
                                                            'johnfirstbook_2_3_6': johnfirstbook_2_3_6,
                                                            'joh_15_10': joh_15_10,
                                                            'heb_13_20_21': heb_13_20_21,
                                                            'bible': selected_bible})
