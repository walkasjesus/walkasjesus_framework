from django.urls import path

from callings_app.views.detail_view import DetailView
from callings_app.views.index_view import IndexView
from callings_app.views.listing_view import ListingView

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('listing', ListingView.as_view(), name='listing'),
    path('detail/<int:calling_id>/', DetailView.as_view(), name='detail'),
]
