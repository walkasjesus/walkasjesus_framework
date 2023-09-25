from django.urls import path

from commandments_app.views.admin.admin_enable_bible import AdminEnableBible
from commandments_app.views.admin.admin_persist_bible_cache import AdminPersistBibleCache
from commandments_app.views.admin.admin_reset_bibles import AdminResetBibles
from commandments_app.views.vision_view import VisionView
from commandments_app.views.legalism_view import LegalismView
from commandments_app.views.termsandconditions_view import TermsView
from commandments_app.views.privacy_view import PrivacyView
from commandments_app.views.detail_view import DetailView, DetailLessonView
from commandments_app.views.index_view import IndexView
from commandments_app.views.listing_view import ListingView, ListingLessonView
from commandments_app.views.user_preferences import UserPreferencesLanguagesView, UserPreferencesBibleView

app_name = 'commandments'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('bible', UserPreferencesBibleView.as_view(), name='bible'),
    path('languages', UserPreferencesLanguagesView.as_view(), name='languages'),
    path('listing', ListingView.as_view(), name='listing'),
    path('lesson', ListingLessonView.as_view(), name='lesson'),
    path('vision', VisionView.as_view(), name='vision'),
    path('legalism', LegalismView.as_view(), name='legalism'),
    path('termsandconditions', TermsView.as_view(), name='termsandconditions'),
    path('privacy', PrivacyView.as_view(), name='privacy'),
    path('detail/<int:commandment_id>', DetailView.as_view(), name='detail'),
    path('lesson/<int:lesson_id>', DetailLessonView.as_view(), name='lessondetail'),

    path('admin/reset_bibles', AdminResetBibles.as_view(), name='admin_reset_bibles'),
    path('admin/persist_bible_cache', AdminPersistBibleCache.as_view(), name='admin_persist_bible_cache'),
    path('admin/enable_bible', AdminEnableBible.as_view(), name='admin_enable_bible'),
]
