from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import gettext_lazy as _

# Import all your views and other necessary modules
from commandments_app.views.admin.admin_enable_bible import AdminEnableBible
from commandments_app.views.admin.admin_persist_bible_cache import AdminPersistBibleCache
from commandments_app.views.admin.admin_reset_bibles import AdminResetBibles
from commandments_app.views.vision_view import VisionView
from commandments_app.views.legalism_view import LegalismView
from commandments_app.views.termsandconditions_view import TermsView
from commandments_app.views.privacy_view import PrivacyView
from commandments_app.views.detail_view import DetailView, DetailLessonView
from commandments_app.views.index_view import IndexView
from commandments_app.views.listing_view import ListingView
from commandments_app.views.listing_lesson_view import ListingLessonView
from commandments_app.views.user_preferences import UserPreferencesLanguagesView, UserPreferencesBibleView

app_name = 'commandments'

# English URL patterns
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('bible/', UserPreferencesBibleView.as_view(), name='bible'),
    path('languages/', UserPreferencesLanguagesView.as_view(), name='languages'),
    path('steps_overview/', ListingView.as_view(), name='listing'),
    path('lessons_overview/', ListingLessonView.as_view(), name='lesson_listing'),
    path('vision/', VisionView.as_view(), name='vision'),
    path('legalism/', LegalismView.as_view(), name='legalism'),
    path('termsandconditions/', TermsView.as_view(), name='termsandconditions'),
    path('privacy/', PrivacyView.as_view(), name='privacy'),
    path('step/<int:commandment_id>/', DetailView.as_view(), name='detail'),
    path('lesson/<int:lesson_id>/', DetailLessonView.as_view(), name='lessondetail'),
    path('admin/reset_bibles/', AdminResetBibles.as_view(), name='admin_reset_bibles'),
    path('admin/persist_bible_cache/', AdminPersistBibleCache.as_view(), name='admin_persist_bible_cache'),
    path('admin/enable_bible/', AdminEnableBible.as_view(), name='admin_enable_bible'),
]

# Dutch URL patterns
urlpatterns += [
    path(_('bijbel/'), UserPreferencesBibleView.as_view(), name='bible'),
    path(_('talen/'), UserPreferencesLanguagesView.as_view(), name='languages'),
    path(_('stappen_overzicht/'), ListingView.as_view(), name='listing'),
    path(_('lessen_overzicht/'), ListingLessonView.as_view(), name='lesson_listing'),
    path(_('visie/'), VisionView.as_view(), name='vision'),
    path(_('wetticisme/'), LegalismView.as_view(), name='legalism'),
    path(_('voorwaarden/'), TermsView.as_view(), name='termsandconditions'),
    path(_('privacy/'), PrivacyView.as_view(), name='privacy'),
    path(_('stap/<int:commandment_id>/'), DetailView.as_view(), name='detail'),
    path(_('les/<int:lesson_id>/'), DetailLessonView.as_view(), name='lessondetail'),
    path(_('admin/herstel_bijbels/'), AdminResetBibles.as_view(), name='admin_reset_bibles'),
    path(_('admin/cache_bijbel_opslaan/'), AdminPersistBibleCache.as_view(), name='admin_persist_bible_cache'),
    path(_('admin/activeer_bijbel/'), AdminEnableBible.as_view(), name='admin_enable_bible'),
]