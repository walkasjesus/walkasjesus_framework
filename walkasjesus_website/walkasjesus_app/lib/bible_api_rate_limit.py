import hashlib
import ipaddress
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from walkasjesus_app.models import BibleTranslationUsageDaily


class BibleApiRateLimitExceeded(Exception):
    def __init__(self, message, limit, count):
        super().__init__(message)
        self.message = message
        self.limit = limit
        self.count = count


def bible_api_rate_limit_message():
    return str(getattr(
        settings,
        'BIBLE_API_RATE_LIMIT_MESSAGE',
        'The daily Bible API limit has been reached for this device. Please try again tomorrow.',
    ))


def _client_ip(request):
    candidates = [
        request.META.get('HTTP_X_REAL_IP'),
        request.META.get('HTTP_CF_CONNECTING_IP'),
        request.META.get('REMOTE_ADDR'),
    ]

    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        candidates.extend(part.strip() for part in forwarded_for.split(','))

    for candidate in candidates:
        value = str(candidate or '').strip()
        if not value:
            continue
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            continue
    return ''


def _is_whitelisted_ip(ip_address):
    if not ip_address:
        return False

    try:
        client_ip = ipaddress.ip_address(ip_address)
    except ValueError:
        return False

    for value in getattr(settings, 'BIBLE_API_RATE_LIMIT_WHITELIST', []) or []:
        value = str(value or '').strip()
        if not value:
            continue
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            continue
        if client_ip in network:
            return True
    return False


def _user_identity(request):
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        raw_identifier = f'auth:{getattr(user, "pk", "")}'
        return BibleTranslationUsageDaily.USER_AUTHENTICATED, hashlib.sha256(raw_identifier.encode('utf-8')).hexdigest()[:32]

    session_key = getattr(getattr(request, 'session', None), 'session_key', None)
    if not session_key and hasattr(request, 'session'):
        request.session.save()
        session_key = request.session.session_key

    remote_addr = _client_ip(request)
    user_agent = str(request.META.get('HTTP_USER_AGENT', '') or '').strip()
    raw_identifier = f'anon:{session_key or "no-session"}:{remote_addr}:{user_agent}'
    return BibleTranslationUsageDaily.USER_ANONYMOUS, hashlib.sha256(raw_identifier.encode('utf-8')).hexdigest()[:32]


def _seconds_until_tomorrow():
    now = timezone.localtime(timezone.now())
    tomorrow = datetime.combine(now.date() + timedelta(days=1), time.min)
    tomorrow = timezone.make_aware(tomorrow, now.tzinfo)
    return max(60, int((tomorrow - now).total_seconds()) + 60)


def _record_blocked_usage(request, bible, endpoint):
    user_kind, user_key = _user_identity(request)
    usage_date = timezone.now().date()
    bible_id = str(getattr(bible, 'id', '') or getattr(bible, 'bible_id', '') or bible or '').strip() or 'unknown'
    bible_name = str(getattr(bible, 'name', '') or '').strip()
    bible_language = str(getattr(bible, 'language', '') or '').strip().upper()[:8]

    try:
        with transaction.atomic():
            row = BibleTranslationUsageDaily.objects.select_for_update().filter(
                usage_date=usage_date,
                bible_id=bible_id,
                source=BibleTranslationUsageDaily.SOURCE_BLOCKED,
                endpoint=endpoint,
                user_key=user_key,
            ).first()
            if row:
                row.request_count += 1
                row.user_kind = user_kind
                row.bible_name = bible_name
                row.bible_language = bible_language
                row.save(update_fields=['request_count', 'user_kind', 'bible_name', 'bible_language', 'updated_at'])
            else:
                BibleTranslationUsageDaily.objects.create(
                    usage_date=usage_date,
                    bible_id=bible_id,
                    bible_name=bible_name,
                    bible_language=bible_language,
                    source=BibleTranslationUsageDaily.SOURCE_BLOCKED,
                    endpoint=endpoint,
                    user_kind=user_kind,
                    user_key=user_key,
                    request_count=1,
                    verse_count=0,
                )
    except Exception:
        pass


def consume_bible_api_quota(request, bible, endpoint, amount=1):
    if not bool(getattr(settings, 'BIBLE_API_RATE_LIMIT_ENABLED', False)):
        return

    client_ip = _client_ip(request)
    if _is_whitelisted_ip(client_ip):
        return

    limit = int(getattr(settings, 'BIBLE_API_DAILY_CALL_LIMIT', 100) or 100)
    if limit <= 0:
        return

    _, user_key = _user_identity(request)
    usage_date = timezone.now().date().isoformat()
    cache_key = f'bible-api-rate-limit:v1:{usage_date}:{user_key}'
    cache.add(cache_key, 0, timeout=_seconds_until_tomorrow())

    try:
        count = cache.incr(cache_key, int(max(1, amount)))
    except ValueError:
        cache.set(cache_key, int(max(1, amount)), timeout=_seconds_until_tomorrow())
        count = int(max(1, amount))

    if count > limit:
        _record_blocked_usage(request, bible, endpoint)
        raise BibleApiRateLimitExceeded(bible_api_rate_limit_message(), limit, count)