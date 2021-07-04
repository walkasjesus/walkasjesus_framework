from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment


class ListingView(View):
    def get(self, request):
        commandments_ordered = Commandment.objects.order_by('id').all().prefetch_related('drawing_set')
        return render(request, 'commandments/listing.html', {'commandments': commandments_ordered,
                                                               'commandments_total': Commandment.objects.count()})

