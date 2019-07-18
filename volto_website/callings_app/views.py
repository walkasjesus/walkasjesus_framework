from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse

from callings_app.models import Calling


def index(request):
    calling_list = Calling.objects.order_by('quote')[:20]
    output = '\n '.join([c.quote for c in calling_list])
    return render(request, 'calling/index.html', {'calling_list': calling_list})


def detail(request, calling_id):
    calling = get_object_or_404(Calling, pk=calling_id)
    return render(request, 'calling/detail.html', {'calling': calling})
