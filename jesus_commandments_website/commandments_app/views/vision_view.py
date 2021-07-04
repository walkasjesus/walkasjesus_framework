from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleReference, BibleBooks, UserPreferences


class VisionView(View):
    def get(self, request):

        selected_bible = UserPreferences(request.session).bible
        
        joh_3_16 = BibleReference(selected_bible, BibleBooks.John, 3, 16, 3, 16)
        joh_14_15 = BibleReference(selected_bible, BibleBooks.John, 14, 15, 14, 15)
        joh_14_21 = BibleReference(selected_bible, BibleBooks.John, 14, 21, 14, 21)
        mat_7_24_27 = BibleReference(selected_bible, BibleBooks.Matthew, 7, 24, 7, 27)
        mat_13_18_23 = BibleReference(selected_bible, BibleBooks.Matthew, 13, 18, 13, 23)
        mat_28_18_20 = BibleReference(selected_bible, BibleBooks.Matthew, 28, 19, 28, 20)
        heb_13_20_21 = BibleReference(selected_bible, BibleBooks.Hebrews, 13, 20, 13, 21)

        return render(request, 'commandments/vision.html', {'mat_7_24_27': mat_7_24_27,
                                                            'joh_3_16': joh_3_16,
                                                            'joh_14_15': joh_14_15,
                                                            'joh_14_21': joh_14_21,
                                                            'mat_13_18_23': mat_13_18_23,
                                                            'mat_28_18_20': mat_28_18_20,
                                                            'heb_13_20_21': heb_13_20_21,
                                                            'commandments_total': Commandment.objects.count(),
                                                            'bible': selected_bible})
