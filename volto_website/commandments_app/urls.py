from django.urls import path

from commandments_app.views.bible_view import BibleView
from commandments_app.views.detail_view import DetailView
from commandments_app.views.index_view import IndexView
from commandments_app.views.listing_view import ListingView
from commandments_app.views.study_listing_view import StudyListingView

app_name = 'commandments'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('bible', BibleView.as_view(), name='bible'),
    path('listing', ListingView.as_view(), name='listing'),
    path('study_listing/<str:bible_id>', StudyListingView.as_view(), name='study_listing'),
    path('detail/<str:bible_id>/<int:commandment_id>', DetailView.as_view(), name='detail'),
]
