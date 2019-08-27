from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment


class ListingView(View):
    def get(self, request):
        commandments = list(Commandment.objects.all())
        commandments.sort(key=lambda x: x.primary_bible_reference())

        return render(request, 'commandments/listing.html', {'commandments': commandments})
