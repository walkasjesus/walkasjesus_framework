"""
Middleware for geo-location and language-based redirection.

This middleware checks the user's location and language preference
and redirects them to the appropriate domain:
- Dutch users/language → acc.wandelalsjezus.nl
- Others → acc.walkasjesus.org
"""

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin


CROSS_DOMAIN_LANG_PARAM = '__waj_lang'
CROSS_DOMAIN_BIBLE_PARAM = '__waj_bible'


class GeoLocationRedirectMiddleware(MiddlewareMixin):
    """
    Redirect users based on location and language preference.
    
    Configuration (in settings.py):
    - GEO_REDIRECT_ENABLED: Enable/disable this middleware
    - GEO_REDIRECT_NL_DOMAIN: Dutch domain (e.g., 'acc.wandelalsjezus.nl')
    - GEO_REDIRECT_EN_DOMAIN: English fallback domain (e.g., 'acc.walkasjesus.org')
    
    Priority:
    1. Language preference (if Dutch is selected, go to Dutch domain)
    2. GeoIP location (if from Netherlands, go to Dutch domain)
    3. Default to English domain
    """
    
    def process_request(self, request):
        # Check if geo-redirect is enabled
        geo_redirect_enabled = os.getenv('GEO_REDIRECT_ENABLED', 'false').lower() == 'true'
        if not geo_redirect_enabled:
            return None
        
        from django.conf import settings
        from django.utils.translation import get_language
        
        if not hasattr(settings, 'GEO_REDIRECT_ENABLED') or not settings.GEO_REDIRECT_ENABLED:
            return None
        
        current_host = request.get_host().split(':')[0]  # Remove port if present
        nl_domain = getattr(settings, 'GEO_REDIRECT_NL_DOMAIN', 'acc.wandelalsjezus.nl')
        en_domain = getattr(settings, 'GEO_REDIRECT_EN_DOMAIN', 'acc.walkasjesus.org')

        # Handle one-time cross-domain language handoff and set cookie on this host.
        handoff_lang = str(request.GET.get(CROSS_DOMAIN_LANG_PARAM, '')).strip().lower()
        supported_languages = {code for code, _ in getattr(settings, 'LANGUAGES', [])}
        if handoff_lang in supported_languages:
            handoff_bible = str(request.GET.get(CROSS_DOMAIN_BIBLE_PARAM, '')).strip()
            try:
                from django.utils import translation
                translation.activate(handoff_lang)
            except Exception:
                pass

            if handoff_bible and handoff_bible not in getattr(settings, 'DISABLED_BIBLE_TRANSLATIONS', []):
                try:
                    from walkasjesus_app.models import BibleTranslation, UserPreferences

                    candidate = BibleTranslation().get(handoff_bible)
                    if str(getattr(candidate, 'language', '')).strip().lower() == handoff_lang:
                        UserPreferences(request.session).bible = candidate
                except Exception:
                    pass

            split = urlsplit(request.get_full_path())
            kept_query = [
                (key, value)
                for key, value in parse_qsl(split.query, keep_blank_values=True)
                if key not in {CROSS_DOMAIN_LANG_PARAM, CROSS_DOMAIN_BIBLE_PARAM}
            ]
            clean_path = urlunsplit(('', '', split.path or '/', urlencode(kept_query, doseq=True), split.fragment))
            response = HttpResponseRedirect(clean_path)
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                handoff_lang,
                max_age=getattr(settings, 'LANGUAGE_COOKIE_AGE', None),
                path=getattr(settings, 'LANGUAGE_COOKIE_PATH', '/'),
                domain=getattr(settings, 'LANGUAGE_COOKIE_DOMAIN', None),
                secure=getattr(settings, 'LANGUAGE_COOKIE_SECURE', False),
                httponly=getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False),
                samesite=getattr(settings, 'LANGUAGE_COOKIE_SAMESITE', None),
            )
            return response
        
        # Only trust explicit language cookie for cross-domain routing decisions.
        current_lang = str(request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, '')).strip().lower()
        if not current_lang:
            # Fallback only when there is no language preference cookie.
            try:
                current_lang = get_language() or ''
            except Exception:
                current_lang = ''
        
        # Check if user prefers Dutch language
        if current_lang.lower().startswith('nl'):
            target_domain = nl_domain
        else:
            # Check GeoIP location
            geo_country = request.META.get('HTTP_GEO_COUNTRY', '').upper()
            cf_country = request.META.get('HTTP_CF_COUNTRY', '').upper()  # Cloudflare header
            
            if geo_country == 'NL' or cf_country == 'NL':
                target_domain = nl_domain
            else:
                target_domain = en_domain
        
        # Redirect if necessary
        if current_host != target_domain:
            forwarded_proto = str(request.META.get('HTTP_X_FORWARDED_PROTO', '')).strip().lower()
            scheme = getattr(settings, 'GEO_REDIRECT_SCHEME', 'https')
            if request.is_secure():
                scheme = 'https'
            elif forwarded_proto in ('http', 'https'):
                scheme = forwarded_proto

            redirect_url = f'{scheme}://{target_domain}{request.path_info}'
            if request.GET:
                redirect_url += '?' + request.GET.urlencode()
            return HttpResponseRedirect(redirect_url)
        
        return None
