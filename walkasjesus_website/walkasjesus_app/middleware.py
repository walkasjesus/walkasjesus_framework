import hashlib

from django.db import transaction
from django.utils import timezone

from walkasjesus_app.models import PageVisitDaily

from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from django.utils import translation
from django.utils.translation import get_language


class LocalizedUrlRedirectMiddleware:
    """Redirect English URL slugs to their localized equivalents for non-default languages.

    Runs after LocaleMiddleware so the language is already set from the cookie/domain.
    URL slug translations come from gettext_lazy() strings in urls.py and their
    corresponding .po file entries — nothing is hardcoded here.
    To add a new language: translate URL strings in its .po file only.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._default_lang_prefix = settings.LANGUAGE_CODE[:2].lower()

    def __call__(self, request):
        language = get_language()  # Already set by LocaleMiddleware from cookie/domain.
        if language and language[:2].lower() != self._default_lang_prefix:
            # Resolve the current path in the default (English) language context.
            # The path may still be in English (e.g. /law_of_messiah/) even though
            # the user's preferred language is Dutch.
            match = None
            with translation.override(settings.LANGUAGE_CODE):
                try:
                    match = resolve(request.path)
                except Resolver404:
                    pass  # Already a localized URL or unknown path — no redirect needed.

            if match is not None and match.view_name:
                # Reverse with the active language to get the localized URL.
                with translation.override(language):
                    try:
                        localized = reverse(
                            match.view_name, args=match.args, kwargs=match.kwargs
                        )
                    except NoReverseMatch:
                        localized = request.path

                if localized != request.path:
                    query = request.META.get('QUERY_STRING', '')
                    return HttpResponseRedirect(localized + ('?' + query if query else ''))

        return self.get_response(request)


class PermissionsPolicyMiddleware:
    """Set a permissive policy for embedded media players."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Permissions-Policy'] = (
            'picture-in-picture=(self "https://www.youtube.com" "https://www.youtube-nocookie.com")'
        )
        return response


class PageUsageTrackingMiddleware:
    """Track daily page visits for non-admin site pages."""

    EXCLUDED_PREFIXES = (
        '/static/',
        '/media/',
        '/admin_portal/',
        '/__debug__/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            self._track_request(request, response)
        except Exception:
            # Never break request handling due to analytics collection.
            pass

        return response

    def _user_identity(self, request):
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            raw_identifier = f'auth:{getattr(user, "pk", "")}'
            return PageVisitDaily.USER_AUTHENTICATED, hashlib.sha256(raw_identifier.encode('utf-8')).hexdigest()[:32]

        session_key = getattr(getattr(request, 'session', None), 'session_key', None)
        if not session_key and hasattr(request, 'session'):
            request.session.save()
            session_key = request.session.session_key

        remote_addr = str(request.META.get('REMOTE_ADDR', '') or '').strip()
        user_agent = str(request.META.get('HTTP_USER_AGENT', '') or '').strip()
        raw_identifier = f'anon:{session_key or "no-session"}:{remote_addr}:{user_agent}'
        return PageVisitDaily.USER_ANONYMOUS, hashlib.sha256(raw_identifier.encode('utf-8')).hexdigest()[:32]

    def _track_request(self, request, response):
        if request.method != 'GET':
            return
        if int(getattr(response, 'status_code', 0) or 0) >= 400:
            return

        path = str(getattr(request, 'path', '') or '')
        if not path or any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return

        usage_date = timezone.now().date()
        language_code = str(getattr(request, 'LANGUAGE_CODE', '') or '').strip().lower()[:8]
        resolver_match = getattr(request, 'resolver_match', None)
        page_label = str(getattr(resolver_match, 'view_name', '') or '').strip() or path
        user_kind, user_key = self._user_identity(request)

        with transaction.atomic():
            row = PageVisitDaily.objects.select_for_update().filter(
                usage_date=usage_date,
                page_path=path,
                language_code=language_code,
                user_key=user_key,
            ).first()
            if row:
                row.visit_count += 1
                row.user_kind = user_kind
                row.page_label = page_label
                row.save(update_fields=['visit_count', 'user_kind', 'page_label', 'updated_at'])
            else:
                PageVisitDaily.objects.create(
                    usage_date=usage_date,
                    page_path=path,
                    page_label=page_label,
                    language_code=language_code,
                    user_kind=user_kind,
                    user_key=user_key,
                    visit_count=1,
                )
