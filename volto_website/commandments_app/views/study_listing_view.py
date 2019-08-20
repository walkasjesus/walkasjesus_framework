from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment, UserPreferences


class StudyListingView(View):
    def get(self, request):
        commandments = list(Commandment.objects.all())
        # TODO this will fail if no prim bible ref! Maybe should be one on one relation in model?
        commandments.sort(key=lambda x: x.primary_bible_references()[0])

        primary_bible_references = []
        secondary_bible_references = []
        tertiary_bible_references = []

        user_bible = UserPreferences(request.session).bible

        for commandment in commandments:
            commandment.bible = user_bible

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
