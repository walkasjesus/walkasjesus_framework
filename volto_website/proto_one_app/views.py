from django.shortcuts import render
from django.http import HttpResponse

from proto_one_app.models import Calling


def index(request):
    calling_list = Calling.objects.order_by('quote')[:20]
    output = '\n '.join([c.quote for c in calling_list])
    return HttpResponse(output)
