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
