from django.shortcuts import render, get_object_or_404
from django.views import View

from commandments_app.models import Commandment, UserPreferences


class DetailView(View):
    def get(self, request, commandment_id):
        commandment = get_object_or_404(Commandment, pk=commandment_id)
        commandment.bible = UserPreferences(request.session).bible
        return render(request, 'commandments/detail.html', {'commandment': commandment})
