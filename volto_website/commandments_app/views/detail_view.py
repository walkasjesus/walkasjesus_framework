from django.shortcuts import render, get_object_or_404
from django.views import View

from commandments_app.models import Commandment


class DetailView(View):
    def get(self, request, commandment_id):
        commandment = get_object_or_404(Commandment, pk=commandment_id)

        primary_bible_references = commandment.primary_bible_references()
        for bible_reference in primary_bible_references:
            bible_reference.load_text()
            secondary_bible_references = commandment.primary_bible_references()
        for bible_reference in secondary_bible_references:
            bible_reference.load_text()

        background_song = commandment.songs()[0] if commandment.songs() else ''
        background_image = commandment.images()[0] if commandment.images() else ''

        return render(request, 'commandments/detail.html', {'commandment': commandment,
                                                            'background_song': background_song,
                                                            'background_image': background_image,
                                                            'primary_bible_references': primary_bible_references,
                                                            'secondary_bible_references': secondary_bible_references,
                                                            'questions': commandment.questions(),
                                                            'songs': commandment.songs(),
                                                            'videos': commandment.videos(),
                                                            'sermons': commandment.sermons(),
                                                            'images': commandment.images()})
