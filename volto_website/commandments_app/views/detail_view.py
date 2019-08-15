from django.shortcuts import render, get_object_or_404
from django.views import View

from commandments_app.models import Commandment


class DetailView(View):
    def get(self, request, commandment_id):
        commandment = get_object_or_404(Commandment, pk=commandment_id)

        primary_bible_references = commandment.primary_bible_references()
        for bible_reference in primary_bible_references:
            bible_reference.load_text()

        secondary_bible_references = commandment.secondary_bible_references()
        for bible_reference in secondary_bible_references:
            bible_reference.load_text()

        tertiary_bible_references = commandment.tertiary_bible_references()
        for bible_reference in tertiary_bible_references:
            bible_reference.load_text()

        background_song = commandment.songs()[0] if commandment.songs() else ''

        return render(request, 'commandments/detail.html', {'commandment': commandment,
                                                            'background_song': background_song,
                                                            'background_drawing': commandment.background_drawing(),
                                                            'primary_bible_references': primary_bible_references,
                                                            'secondary_bible_references': secondary_bible_references,
                                                            'tertiary_bible_references': tertiary_bible_references,
                                                            'questions': commandment.questions(),
                                                            'songs': commandment.songs(),
                                                            'movies': commandment.movies(),
                                                            'shortmovies': commandment.shortmovies(),
                                                            'sermons': commandment.sermons(),
                                                            'pictures': commandment.pictures(),
                                                            'testimonies': commandment.testimonies(),
                                                            'books': commandment.books(),
                                                            'drawings': commandment.drawings()})
