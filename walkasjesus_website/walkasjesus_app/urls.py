from django.urls import path
from django.utils.translation import gettext_lazy as _

# Import all your views and other necessary modules
from walkasjesus_app.views.admin.admin_enable_bible import AdminEnableBible
from walkasjesus_app.views.admin.admin_persist_bible_cache import AdminPersistBibleCache
from walkasjesus_app.views.admin.admin_reset_bibles import AdminResetBibles
from walkasjesus_app.views.vision_view import VisionView
from walkasjesus_app.views.legalism_view import LegalismView
from walkasjesus_app.views.termsandconditions_view import TermsView
from walkasjesus_app.views.privacy_view import PrivacyView
from walkasjesus_app.views.detail_view import DetailView, DetailLessonView, BibleVersesCommandmentView, BibleVersesLessonView
from walkasjesus_app.views.index_view import IndexView
from walkasjesus_app.views.listing_view import ListingView
from walkasjesus_app.views.listing_lesson_view import ListingLessonView
from walkasjesus_app.views.law_of_messiah_view import (
    LawOfMessiahListingView,
    LawOfMessiahDetailView,
    LawOfMessiahBibleVersesView,
)
from walkasjesus_app.views.user_preferences import UserPreferencesLanguagesView, UserPreferencesBibleView, BibleTranslationsForLanguageView
from walkasjesus_app.views.user_preferences import (
    CommentaryTranslationView,
    ScripturaCommentaryProxyView,
    UserPreferencesLanguageSwitchView,
)
from walkasjesus_app.views.maimonides_view import MaimonidesBibleVersesView, MaimonidesList

app_name = 'commandments'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('language-switch/', UserPreferencesLanguageSwitchView.as_view(), name='language_switch'),
    path(_('bible/'), UserPreferencesBibleView.as_view(), name='bible'),
    path(_('languages/'), UserPreferencesLanguagesView.as_view(), name='languages'),
    path(_('bible-translations/'), BibleTranslationsForLanguageView.as_view(), name='bible_translations_for_language'),
    path(_('commentary-translate/'), CommentaryTranslationView.as_view(), name='commentary_translate'),
    path(_('commentary-scriptura/'), ScripturaCommentaryProxyView.as_view(), name='commentary_scriptura'),
    path(_('steps/'), ListingView.as_view(), name='listing'),
    path(_('lessons/'), ListingLessonView.as_view(), name='lesson_listing'),
    path(_('maimonides/'), MaimonidesList.as_view(), name='maimonides_listing'),
    path(_('maimonides/<str:maimonides_id>/verses/'), MaimonidesBibleVersesView.as_view(), name='maimonides_verses'),
    path(_('law_of_messiah/'), LawOfMessiahListingView.as_view(), name='law_of_messiah_listing'),
    path(_('law_of_messiah/<str:law_id>/'), LawOfMessiahDetailView.as_view(), name='law_of_messiah_detail'),
    path(_('law_of_messiah/<str:law_id>/verses/'), LawOfMessiahBibleVersesView.as_view(), name='law_of_messiah_verses'),
    path(_('vision/'), VisionView.as_view(), name='vision'),
    path(_('legalism/'), LegalismView.as_view(), name='legalism'),
    path(_('termsandconditions/'), TermsView.as_view(), name='termsandconditions'),
    path(_('privacy/'), PrivacyView.as_view(), name='privacy'),
    path(_('step/<int:commandment_id>/'), DetailView.as_view(), name='detail'),
    path(_('step/<int:commandment_id>/verses/'), BibleVersesCommandmentView.as_view(), name='commandment_verses'),
    path(_('lesson/<int:lesson_id>/'), DetailLessonView.as_view(), name='lessondetail'),
    path(_('lesson/<int:lesson_id>/verses/'), BibleVersesLessonView.as_view(), name='lesson_verses'),
    path(_('admin/reset_bibles/'), AdminResetBibles.as_view(), name='admin_reset_bibles'),
    path(_('admin/persist_bible_cache/'), AdminPersistBibleCache.as_view(), name='admin_persist_bible_cache'),
    path(_('admin/enable_bible/'), AdminEnableBible.as_view(), name='admin_enable_bible'),
]