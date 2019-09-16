from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment


class ListingView(View):
    def get(self, request):
        return render(request, 'commandments/listing.html', {'commandments': Commandment.objects.order_by('id').all()})
