from django.core.paginator import Paginator
from django.shortcuts import render
from django.views import View

from callings_app.models import Calling


class ListingView(View):
    def get(self, request):
        number_of_items = 25
        calling_list = Calling.objects.all()
        paginator = Paginator(calling_list, number_of_items)

        page = request.GET.get('page')
        callings = paginator.get_page(page)
        return render(request, 'callings/listing.html', {'callings': callings})
