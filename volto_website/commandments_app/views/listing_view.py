from django.core.paginator import Paginator
from django.shortcuts import render
from django.views import View

from commandments_app.models import Commandment


class ListingView(View):
    def get(self, request):
        number_of_items = 25
        paginator = Paginator(Commandment.objects.all(), number_of_items)

        page = request.GET.get('page')
        commandments = paginator.get_page(page)

        return render(request, 'commandments/listing.html', {'commandments': commandments})
