from django.shortcuts import render, get_object_or_404
from django.views import View

from callings_app.models import Calling


class DetailView(View):
    def get(self, request, calling_id):
        calling = get_object_or_404(Calling, pk=calling_id)
        bible_references = calling.bible_references()
        for bible_reference in bible_references:
            bible_reference.load_text()
        images = calling.images()
        return render(request, 'callings/detail.html', {'calling': calling,
                                                        'bible_references': bible_references,
                                                        'images': images})
