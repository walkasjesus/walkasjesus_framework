from django.shortcuts import render, get_object_or_404
from django.views import View

from commandments_app.models import Commandment


class StudyListingView(View):
    def get(self, request):
        commandments = Commandment.objects.all()

        primary_bible_references = []
        secondary_bible_references = []
        tertiary_bible_references = []

        for commandment in commandments:
            for bible_reference in commandment.primary_bible_references():
                entry = {'commandment': commandment,
                         'bible_reference': bible_reference}
                primary_bible_references.append(entry)

            for bible_reference in commandment.secondary_bible_references():
                entry = {'commandment': commandment,
                         'bible_reference': bible_reference}
                secondary_bible_references.append(entry)

            for bible_reference in commandment.tertiary_bible_references():
                entry = {'commandment': commandment,
                         'bible_reference': bible_reference}
                tertiary_bible_references.append(entry)

        return render(request, 'commandments/study_listing.html', {'primary_bible_references': primary_bible_references,
                                                                   'secondary_bible_references': secondary_bible_references,
                                                                   'tertiary_bible_references': tertiary_bible_references})
