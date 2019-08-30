from django.urls import path

from commandments_app.views.bible_admin_view import BibleAdminView
from commandments_app.views.bible_detail_admin_view import BibleDetailAdminView
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
    path('study_listing', StudyListingView.as_view(), name='study_listing'),
    path('detail/<int:commandment_id>', DetailView.as_view(), name='detail'),

    # Todo rename urls
    path('temp', BibleAdminView.as_view(), name='temp'),
    path('temp_detail/<str:bible_id>', BibleDetailAdminView.as_view(), name='temp_detail'),
]
