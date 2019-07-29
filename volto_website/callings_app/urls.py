from django.urls import path

from callings_app.views.demo_view import DemoView
from callings_app.views.detail_view import DetailView
from callings_app.views.index_view import IndexView
from callings_app.views.listing_view import ListingView


app_name = 'callings'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('demo', DemoView.as_view(), name='demo'),
    path('listing', ListingView.as_view(), name='listing'),
    path('detail/<int:calling_id>/', DetailView.as_view(), name='detail'),
]
