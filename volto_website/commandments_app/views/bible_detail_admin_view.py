from bible_lib import BibleFactory
from django.conf import settings
from django.shortcuts import render
from django.views import View

from commandments_app.models import BibleReferences


class BibleDetailAdminView(View):
    def get(self, request, bible_id: str):
        if not settings.DEBUG:
            raise Exception('Not implemented login for this page')

        bible = BibleFactory().create(bible_id)
        bible_references = BibleReferences()
        bible_references.bible = bible

        return render(request, 'admin/bible_detail_admin.html', {'bible': bible,
                                                                 'bible_references': bible_references})
