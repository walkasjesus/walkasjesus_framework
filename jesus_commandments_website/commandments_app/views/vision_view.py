from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleReference, BibleBooks, UserPreferences


class VisionView(View):
    def get(self, request):

        selected_bible = UserPreferences(request.session).bible

        matt_13_4_9 = BibleReference(selected_bible, BibleBooks.Matthew, 13, 4, 13, 9)
        matt_13_18_23 = BibleReference(selected_bible, BibleBooks.Matthew, 13, 18, 13, 23)
        matt_28_19_20 = BibleReference(selected_bible, BibleBooks.Matthew, 28, 19, 28, 20)
        heb_13_20_21 = BibleReference(selected_bible, BibleBooks.Hebrews, 13, 20, 13, 21)

        return render(request, 'commandments/vision.html', {'matt_13_4_9': matt_13_4_9,
                                                            'matt_13_18_23': matt_13_18_23,
                                                            'matt_28_19_20': matt_28_19_20,
                                                            'heb_13_20_21': heb_13_20_21,
                                                            'bible': selected_bible})