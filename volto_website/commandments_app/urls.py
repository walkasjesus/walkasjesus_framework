from django.urls import path

from commandments_app.views.admin_bible_view import AdminBibleView
from commandments_app.views.admin_cache_bible import AdminCacheBible
from commandments_app.views.admin_reset_bibles import AdminResetBibles
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
    path('admin_bible', AdminBibleView.as_view(), name='admin_bible'),
    path('admin_reset_bibles', AdminResetBibles.as_view(), name='admin_reset_bibles'),
    path('admin_cache_bible', AdminCacheBible.as_view(), name='admin_cache_bible'),
]
