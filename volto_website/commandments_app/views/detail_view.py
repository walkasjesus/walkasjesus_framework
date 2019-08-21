from bible_lib import BibleFactory
from django.shortcuts import render, get_object_or_404
from django.views import View

from commandments_app.models import Commandment


class DetailView(View):
    def get(self, request, bible_id: str, commandment_id: int ):
        commandment = get_object_or_404(Commandment, pk=commandment_id)
        commandment.bible = BibleFactory().create(bible_id)
        return render(request, 'commandments/detail.html', {'commandment': commandment})
