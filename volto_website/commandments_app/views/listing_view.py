from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment


class ListingView(View):
    def get(self, request):
        commandments = list(Commandment.objects.all())
        # TODO this will fail if no prim bible ref! Maybe should be one on one relation in model?
        commandments.sort(key=lambda x: x.primary_bible_references()[0])

        return render(request, 'commandments/listing.html', {'commandments': commandments})
