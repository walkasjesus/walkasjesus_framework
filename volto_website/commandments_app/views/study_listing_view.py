from bible_lib import BibleFactory
from bible_lib.performance_time_decorator import performance_time
from django.shortcuts import render
from django.core.cache import cache
from django.utils import translation
from django.views import View

from commandments_app.models import Commandment


class StudyListingView(View):
    def get(self, request, bible_id: str):
        cache_key = translation.get_language() + '.StudyListingViewContext'
        if cache_key not in cache:
            cache.set(cache_key, self._get_data_context(bible_id), 60*60)

        return render(request, 'commandments/study_listing.html', cache.get(cache_key))

    @performance_time
    def _get_data_context(self, bible_id):
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
