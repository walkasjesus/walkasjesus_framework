import re

from django.http import HttpResponseRedirect
from django.utils.translation import get_language


# Mapping of English URL prefixes to their Dutch equivalents for user-facing pages.
_DUTCH_URL_MAP = [
    (r'^/law_of_messiah/([^/]+)/$', '/wet_van_christus/{}/'),
    (r'^/law_of_messiah/$', '/wet_van_christus/'),
]
_DUTCH_URL_PATTERNS = [(re.compile(pat), repl) for pat, repl in _DUTCH_URL_MAP]


class LocalizedUrlRedirectMiddleware:
    """Redirect English law_of_messiah URLs to their Dutch equivalents when language is Dutch."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = (get_language() or 'en')[:2].lower()
        if lang == 'nl':
            path = request.path
            for compiled, replacement in _DUTCH_URL_PATTERNS:
                match = compiled.match(path)
                if match:
                    groups = match.groups()
                    dutch_path = replacement.format(*groups)
                    query = request.META.get('QUERY_STRING', '')
                    if query:
                        dutch_path = dutch_path + '?' + query
                    return HttpResponseRedirect(dutch_path)
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
