from functools import lru_cache

from bible_lib import BibleFactory
from bible_lib.performance_time_decorator import performance_time
from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment


class StudyListingView(View):
    def get(self, request, bible_id: str):
        data_context = self._get_data_context(bible_id)
        return render(request, 'commandments/study_listing.html', data_context)

    @staticmethod
    @performance_time
    @lru_cache(maxsize=None)
    def _get_data_context(bible_id):
        commandments = list(Commandment.objects.all())
        # TODO this will fail if no prim bible ref! Maybe should be one on one relation in model?
        commandments.sort(key=lambda x: x.primary_bible_references()[0])
        primary_bible_references = []
        secondary_bible_references = []
        tertiary_bible_references = []
        user_bible = BibleFactory().create(bible_id)
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

        return {'primary_bible_references': primary_bible_references,
                'secondary_bible_references': secondary_bible_references,
                'tertiary_bible_references': tertiary_bible_references}
