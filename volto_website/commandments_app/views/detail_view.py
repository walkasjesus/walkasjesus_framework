from django.shortcuts import render, get_object_or_404
from django.views import View

from commandments_app.models import Commandment


class DetailView(View):
    def get(self, request, commandment_id):
        commandment = get_object_or_404(Commandment, pk=commandment_id)
        bible_references = commandment.all_bible_references()
        for bible_reference in bible_references:
            bible_reference.load_text()
        images = commandment.images()
        return render(request, 'commandments/detail.html', {'commandment': commandment,
                                                            'bible_references': bible_references,
                                                            'images': images})
