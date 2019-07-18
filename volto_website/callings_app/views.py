from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404

from callings_app.models import Calling


def index(request):
    calling_list = Calling.objects.order_by('quote')[0:20]
    return render(request, 'callings/index.html', {'calling_list': calling_list})


def listing(request):
    number_of_items = 25
    calling_list = Calling.objects.all()
    paginator = Paginator(calling_list, number_of_items)

    page = request.GET.get('page')
    callings = paginator.get_page(page)
    return render(request, 'callings/listing.html', {'callings': callings})


def detail(request, calling_id):
    calling = get_object_or_404(Calling, pk=calling_id)
    return render(request, 'callings/detail.html', {'calling': calling})
