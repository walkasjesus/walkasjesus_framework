import logging
import re
from urllib.parse import urlparse

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from walkasjesus_app.lib.access_policy import is_bible_id_visible_for_request
from walkasjesus_app.media_image_utils import media_file_exists
from walkasjesus_app.models import BibleTranslation, LawOfMessiah, LawOfMessiahDrawing, Lesson, Maimonides, UserPreferences
from walkasjesus_app.views.detail_view import (
    _allowed_media_languages,
    _allowed_target_audiences,
    _filter_grouped_media_by_audience,
    _step_to_law_mapping,
)


VERSE_CACHE_TIMEOUT = int(getattr(settings, 'BIBLE_API_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))


def _normalize_image_url(url):
    if not url:
        return ''
    value = str(url).strip()
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if value.startswith('/media/') or value.startswith('/static/'):
        return value
    if value.startswith('/'):
        # Keep absolute non-media paths unchanged for backward compatibility.
        return value

    media_prefix = (settings.MEDIA_URL or '/media/').rstrip('/') + '/'
    if value.startswith('media/'):
        value = value[len('media/'):]
    return media_prefix + value.lstrip('/')


def _is_http_url(value):
    candidate = str(value or '').strip()
    if not candidate:
        return False
    parsed = urlparse(candidate)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _find_primary_drawing(law):
    for related_step in law.related_steps.all().order_by('id'):
        step_drawing = related_step.background_drawing()
        if step_drawing and step_drawing.img_url and media_file_exists(step_drawing.img_url):
            return step_drawing

    for drawing in law.media.all():
        if drawing.media_type == LawOfMessiahDrawing.MEDIA_TYPE_DRAWING and drawing.img_url and media_file_exists(drawing.img_url):
            return drawing
    return None


def _law_media_type_order():
    return [
        LawOfMessiahDrawing.MEDIA_TYPE_DRAWING,
        LawOfMessiahDrawing.MEDIA_TYPE_SONG,
        LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK,
        LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW,
        LawOfMessiahDrawing.MEDIA_TYPE_MOVIE,
        LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE,
        LawOfMessiahDrawing.MEDIA_TYPE_WAJVIDEO,
        LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY,
        LawOfMessiahDrawing.MEDIA_TYPE_BLOG,
        LawOfMessiahDrawing.MEDIA_TYPE_PICTURE,
        LawOfMessiahDrawing.MEDIA_TYPE_SERMON,
        LawOfMessiahDrawing.MEDIA_TYPE_BOOK,
    ]


def _collect_law_media_by_type(law):
    grouped = {media_type: [] for media_type in _law_media_type_order()}
    seen = set()

    def is_displayable(media_type, title, description, img_url, url):
        normalized_media_type = str(media_type or '').strip().lower() or LawOfMessiahDrawing.MEDIA_TYPE_DRAWING
        title = str(title or '').strip()
        description = str(description or '').strip()
        img_url = str(img_url or '').strip()
        url = str(url or '').strip()

        if normalized_media_type in {
            LawOfMessiahDrawing.MEDIA_TYPE_SONG,
            LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK,
            LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW,
            LawOfMessiahDrawing.MEDIA_TYPE_MOVIE,
            LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE,
            LawOfMessiahDrawing.MEDIA_TYPE_WAJVIDEO,
            LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY,
            LawOfMessiahDrawing.MEDIA_TYPE_SERMON,
        }:
            return bool(url)

        if normalized_media_type in {
            LawOfMessiahDrawing.MEDIA_TYPE_DRAWING,
            LawOfMessiahDrawing.MEDIA_TYPE_PICTURE,
        }:
            return bool(img_url)

        return bool(title or description or url or img_url)

    def add_item(media_type, title, description, img_url, url, author, target_audience, language, is_public):
        normalized_media_type = str(media_type or '').strip().lower() or LawOfMessiahDrawing.MEDIA_TYPE_DRAWING
        if normalized_media_type not in grouped:
            return
        if not is_displayable(media_type, title, description, img_url, url):
            return
        key = (
            normalized_media_type,
            str(title or '').strip(),
            str(img_url or '').strip(),
            str(url or '').strip(),
            str(author or '').strip(),
        )
        if key in seen:
            return
        seen.add(key)
        grouped[normalized_media_type].append({
            'media_type': normalized_media_type,
            'title': title or '',
            'description': description or '',
            'img_url': _normalize_image_url(img_url),
            'url': url or '',
            'author': author or '',
            'target_audience': target_audience or 'any',
            'language': language or 'any',
            'is_public': bool(is_public),
        })

    for media in law.media.all():
        add_item(
            media_type=media.media_type,
            title=media.title,
            description=media.description,
            img_url=media.img_url,
            url=media.url,
            author=media.author,
            target_audience=media.target_audience,
            language=media.language,
            is_public=media.is_public,
        )

    # Always include media from related steps so BA20-like mappings show shared resources.
    step_media_map = {
        LawOfMessiahDrawing.MEDIA_TYPE_SONG: 'song_set',
        LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK: 'superbook_set',
        LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW: 'henkieshow_set',
        LawOfMessiahDrawing.MEDIA_TYPE_MOVIE: 'movie_set',
        LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE: 'shortmovie_set',
        LawOfMessiahDrawing.MEDIA_TYPE_WAJVIDEO: 'wajvideo_set',
        LawOfMessiahDrawing.MEDIA_TYPE_DRAWING: 'drawing_set',
        LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY: 'testimony_set',
        LawOfMessiahDrawing.MEDIA_TYPE_BLOG: 'blog_set',
        LawOfMessiahDrawing.MEDIA_TYPE_PICTURE: 'picture_set',
        LawOfMessiahDrawing.MEDIA_TYPE_SERMON: 'sermon_set',
        LawOfMessiahDrawing.MEDIA_TYPE_BOOK: 'book_set',
    }
    for step in law.related_steps.all():
        for media_type, relation in step_media_map.items():
            for media in getattr(step, relation).all():
                add_item(
                    media_type=media_type,
                    title=media.title,
                    description=media.description,
                    img_url=media.img_url,
                    url=media.url,
                    author=media.author,
                    target_audience=media.target_audience,
                    language=media.language,
                    is_public=media.is_public,
                )

    related_steps = list(law.related_steps.all())
    related_lessons = list(Lesson.objects.filter(commandment__in=related_steps)) if related_steps else []
    shared_query = LawOfMessiahDrawing.objects.filter(Q(law_of_messiah=law))
    if related_steps:
        shared_query = shared_query | LawOfMessiahDrawing.objects.filter(commandment__in=related_steps)
    if related_lessons:
        shared_query = shared_query | LawOfMessiahDrawing.objects.filter(lesson__in=related_lessons)

    for media in shared_query.distinct():
        add_item(
            media_type=media.media_type,
            title=media.title,
            description=media.description,
            img_url=media.img_url,
            url=media.url,
            author=media.author,
            target_audience=media.target_audience,
            language=media.language,
            is_public=media.is_public,
        )

    return grouped


def _dedupe_drawings_for_display(drawings):
    unique = []
    seen = set()
    for drawing in drawings or []:
        key = (
            str(drawing.get('img_url') or '').strip(),
            str(drawing.get('url') or '').strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(drawing)
    return unique


def _ncla_label_map():
    return {code: label for code, label in LawOfMessiah.NCLA_CHOICES}


def _person_label_map():
    return {
        'JM': _('Jewish male'),
        'JF': _('Jewish female'),
        'KM': _("K'rov Yisrael male"),
        'KF': _("K'rovat Yisrael female"),
        'GM': _('Gentile male'),
        'GF': _('Gentile female'),
    }


def _application_label_map():
    return {
        'm': _('mandated'),
        'r': _('recommended'),
        'o': _('optional'),
        'n': _('not generally recommended'),
        'u': _('unauthorized'),
        'p': _('prohibited'),
        'i': _('impossible'),
    }


def _person_group_metadata():
    return {
        'JEW': {
            'label': _('Jewish'),
            'icon': 'images/s_jew.png',
        },
        'MESSIANIC': {
            'label': _("K'rov Yisrael"),
            'icon': 'images/s_messianic.png',
        },
        'GENTILE': {
            'label': _('Gentile'),
            'icon': 'images/s_gentile.png',
        },
    }


def _application_person_groups(person_codes):
    grouped = {
        'JEW': {'male': False, 'female': False},
        'MESSIANIC': {'male': False, 'female': False},
        'GENTILE': {'male': False, 'female': False},
    }

    for code in person_codes:
        if code == 'JM':
            grouped['JEW']['male'] = True
        elif code == 'JF':
            grouped['JEW']['female'] = True
        elif code == 'KM':
            grouped['MESSIANIC']['male'] = True
        elif code == 'KF':
            grouped['MESSIANIC']['female'] = True
        elif code == 'GM':
            grouped['GENTILE']['male'] = True
        elif code == 'GF':
            grouped['GENTILE']['female'] = True

    metadata = _person_group_metadata()
    items = []
    for key in ['JEW', 'MESSIANIC', 'GENTILE']:
        genders = grouped[key]
        if not genders['male'] and not genders['female']:
            continue
        items.append({
            'key': key,
            'label': metadata[key]['label'],
            'icon': metadata[key]['icon'],
            'male': genders['male'],
            'female': genders['female'],
        })
    return items


def _ncla_filter_options():
    return {
        'person': [
            ('', _('Everyone')),
            ('JM', _('Jewish male')),
            ('JF', _('Jewish female')),
            ('KM', _("K'rov Yisrael male")),
            ('KF', _("K'rovat Yisrael female")),
            ('GM', _('Gentile male')),
            ('GF', _('Gentile female')),
        ],
        'application': [
            ('', _('Any application')),
            ('m', _('Mandated')),
            ('r', _('Recommended')),
            ('o', _('Optional')),
            ('n', _('Not generally recommended')),
            ('u', _('Unauthorized')),
            ('p', _('Prohibited')),
            ('i', _('Impossible')),
        ],
    }


_ACTIVE_APPLICATION_CODES = {'m', 'r', 'o'}


def _extract_ncla_codes(ncla_data):
    """Extract all individual person+application code tokens from structured or legacy ncla data."""
    codes = []
    for entry in ncla_data or []:
        if isinstance(entry, dict):
            codes.extend(entry.get('codes', []))
        elif isinstance(entry, str):
            codes.append(entry)
    return codes


def _ncla_person_codes(ncla_data):
    """Return person group codes (JEW/MESSIANIC/GENTILE) where at least one active code (m/r/o) exists across all groups."""
    grouped = set()
    for code in _extract_ncla_codes(ncla_data):
        if len(code) < 3:
            continue
        if code[-1] not in _ACTIVE_APPLICATION_CODES:
            continue
        person = code[:2]
        if person in {'JM', 'JF'}:
            grouped.add('JEW')
        elif person in {'KM', 'KF'}:
            grouped.add('MESSIANIC')
        elif person in {'GM', 'GF'}:
            grouped.add('GENTILE')
    return sorted(grouped)


def _ncla_summary(ncla_data):
    """Build a human-readable summary, with per-group detail when multiple groups exist."""
    if not ncla_data:
        return {
            'person_categories': _('Not specified'),
            'literal_application': _('Not specified'),
            'literal_application_expanded': _('Not specified'),
            'application_details': [],
            'groups': [],
        }

    person_labels = _person_label_map()
    application_labels = _application_label_map()
    groups_detail = []
    all_person_codes = set()
    all_application_codes = set()
    all_application_people = {}

    for entry in ncla_data:
        if not isinstance(entry, dict):
            continue
        group_name = entry.get('group', 'All')
        codes = entry.get('codes', [])
        detailed = []
        group_application_people = {}
        for code in codes:
            if len(code) >= 3:
                person_code = code[:2]
                application_code = code[-1]
                person_label = person_labels.get(person_code, person_code)
                application_label = application_labels.get(application_code, application_code)
                detailed.append(f'{code} - {person_label}, {application_label}')
                group_application_people.setdefault(application_code, set()).add(person_code)
                all_application_people.setdefault(application_code, set()).add(person_code)
            else:
                detailed.append(code)
        person_set = sorted(set(c[:2] for c in codes if len(c) >= 3))
        app_set = sorted(set(c[-1] for c in codes if len(c) >= 3))
        all_person_codes.update(person_set)
        all_application_codes.update(app_set)
        group_application_details = []
        for application_code in app_set:
            group_person_codes = sorted(group_application_people.get(application_code, set()))
            if not group_person_codes:
                continue
            group_application_details.append({
                'application_code': application_code,
                'application_label': application_labels.get(application_code, application_code),
                'person_codes': group_person_codes,
                'person_labels': [person_labels.get(code, code) for code in group_person_codes],
                'person_groups': _application_person_groups(group_person_codes),
                'summary': _('%(application)s for %(persons)s') % {
                    'application': application_labels.get(application_code, application_code),
                    'persons': ', '.join(person_labels.get(code, code) for code in group_person_codes),
                },
            })
        groups_detail.append({
            'group': group_name,
            'codes': codes,
            'detailed': detailed,
            'person_summary': ', '.join(person_labels.get(p, p) for p in person_set),
            'application_summary': ', '.join(application_labels.get(a, a) for a in app_set),
            'application_details': group_application_details,
        })

    unique_persons = sorted(all_person_codes)
    unique_applications = sorted(all_application_codes)

    if set(unique_persons) == set(person_labels.keys()):
        person_categories = _('Everyone')
    else:
        person_categories = ', '.join(person_labels.get(p, p) for p in unique_persons)

    literal_application = ', '.join(application_labels.get(a, a) for a in unique_applications)
    application_details = []
    for application_code in unique_applications:
        application_person_codes = sorted(all_application_people.get(application_code, set()))
        if not application_person_codes:
            continue
        application_details.append({
            'application_code': application_code,
            'application_label': application_labels.get(application_code, application_code),
            'person_codes': application_person_codes,
            'person_labels': [person_labels.get(code, code) for code in application_person_codes],
            'person_groups': _application_person_groups(application_person_codes),
            'summary': _('%(application)s for %(persons)s') % {
                'application': application_labels.get(application_code, application_code),
                'persons': ', '.join(person_labels.get(code, code) for code in application_person_codes),
            },
        })
    literal_application_expanded = '; '.join(item['summary'] for item in application_details) or literal_application

    return {
        'person_categories': person_categories,
        'literal_application': literal_application,
        'literal_application_expanded': literal_application_expanded,
        'application_details': application_details,
        'groups': groups_detail,
    }


def _matches_ncla_filters(law, person_code, application_code, group_name=''):
    """Match law against person/application/group filters. Checks structured ncla groups."""
    ncla_data = law.ncla or []
    if not ncla_data:
        return not person_code and not application_code and not group_name

    for entry in ncla_data:
        if not isinstance(entry, dict):
            continue
        # Group filter: only look in matching group
        if group_name and entry.get('group', 'All') != group_name:
            continue
        for code in entry.get('codes', []):
            if len(code) < 3:
                continue
            if person_code and not code.startswith(person_code):
                continue
            # When filtering by person only, exclude inactive compliance codes
            if person_code and not application_code and code[-1] not in _ACTIVE_APPLICATION_CODES:
                continue
            if application_code and not code.endswith(application_code):
                continue
            return True
    return False


def _ncla_group_options(commandment_type=LawOfMessiah.COMMANDMENT_TYPE_POSITIVE, unique_filter='true'):
    """Return distinct ncla group names from laws that have ncla_deviation, scoped to current list filters."""
    query = LawOfMessiah.objects.filter(ncla_deviation=True)
    if commandment_type in {
        LawOfMessiah.COMMANDMENT_TYPE_POSITIVE,
        LawOfMessiah.COMMANDMENT_TYPE_NEGATIVE,
        LawOfMessiah.COMMANDMENT_TYPE_BOTH,
    }:
        query = query.filter(commandment_type=commandment_type)
    if unique_filter == 'true':
        query = query.filter(is_unique=True)
    elif unique_filter == 'false':
        query = query.filter(is_unique=False)

    groups = set()
    for ncla_data in query.values_list('ncla', flat=True):
        for entry in (ncla_data or []):
            if isinstance(entry, dict):
                g = entry.get('group', '').strip()
                if g and g != 'All':
                    groups.add(g)
    return sorted(groups)


def _reference_text(ref, bible):
    text, _ = _reference_text_with_source(ref, bible)
    return text


def _reference_text_with_source(ref, bible):
    bible_cache_id = str(getattr(bible, 'id', '') or getattr(bible, 'bible_id', '') or bible)
    copyright_cache_key = f"bible_copyright:v1:{bible_cache_id}"
    cache_key = (
        f"verse_text:v1:{bible_cache_id}:"
        f"{ref.book}:{ref.begin_chapter}:{ref.begin_verse}:{ref.end_chapter}:{ref.end_verse}"
    )
    cached_copyright = cache.get(copyright_cache_key)
    if cached_copyright:
        bible.copyright = cached_copyright

    cached = cache.get(cache_key)
    if cached is not None:
        return cached, 'cache'

    end_chapter = ref.end_chapter if ref.end_chapter else ref.begin_chapter
    end_verse = ref.end_verse if ref.end_verse else ref.begin_verse
    text = bible.verses(BibleLibBibleBooks[ref.book], ref.begin_chapter, ref.begin_verse, end_chapter, end_verse)
    cache.set(cache_key, text, VERSE_CACHE_TIMEOUT)
    if getattr(bible, 'copyright', ''):
        cache.set(copyright_cache_key, bible.copyright, VERSE_CACHE_TIMEOUT)
    return text, 'api'


def _extract_related_law_ids(related_items):
    ids = []
    for related in related_items or []:
        if isinstance(related, dict):
            related_id = str(related.get('id', '')).strip()
        else:
            related_id = str(related).strip()
        if related_id:
            ids.append(_normalize_law_id(related_id))
    return ids


def _normalize_law_id(law_id):
    normalized = str(law_id or '').strip().upper()
    match = re.match(r'^([A-Z]+)(\d+)$', normalized)
    if not match:
        return normalized

    prefix, number = match.groups()
    return f'{prefix}{int(number)}'


def _requested_ref_ids(request):
    requested = []
    requested.extend(request.POST.getlist('verse_refs[]'))
    requested.extend(request.POST.getlist('verse_refs'))

    single = request.POST.get('verse_refs', '')
    if single and ',' in single:
        requested.extend(single.split(','))

    return {str(item).strip() for item in requested if str(item).strip()}


def _normalize_search_text(value):
    return str(value or '').strip().casefold()


class LawOfMessiahListingView(View):
    def get(self, request):
        search_query = request.GET.get('q', '').strip()
        source_dataset = request.GET.get('source_dataset', '').strip().lower()
        commandment_type_param = request.GET.get('commandment_type')
        unique_filter_param = request.GET.get('is_unique')
        default_commandment_type = '' if search_query else LawOfMessiah.COMMANDMENT_TYPE_POSITIVE
        default_unique_filter = '' if search_query else 'true'
        commandment_type = (
            commandment_type_param.strip().lower()
            if commandment_type_param is not None
            else default_commandment_type
        )
        unique_filter = (
            unique_filter_param.strip().lower()
            if unique_filter_param is not None
            else default_unique_filter
        )
        classical_filter = request.GET.get('classical_commandment', '').strip().lower()
        illustration_filter = request.GET.get('illustration', '').strip().lower()
        category = request.GET.get('category', '').strip()
        person_code = request.GET.get('ncla_person', '').strip().upper()
        application_code = request.GET.get('ncla_application', '').strip().lower()
        ncla_group = request.GET.get('ncla_group', '').strip()

        if commandment_type not in {
            LawOfMessiah.COMMANDMENT_TYPE_POSITIVE,
            LawOfMessiah.COMMANDMENT_TYPE_NEGATIVE,
            LawOfMessiah.COMMANDMENT_TYPE_BOTH,
            '',
        }:
            commandment_type = LawOfMessiah.COMMANDMENT_TYPE_POSITIVE

        if illustration_filter not in {'', 'true', 'false'}:
            illustration_filter = ''

        laws_query = LawOfMessiah.objects.order_by('id').prefetch_related(
            'media',
            'related_steps__drawing_set',
            'related_steps__shared_media_resources',
        )
        if unique_filter == 'true':
            laws_query = laws_query.filter(is_unique=True)
        elif unique_filter == 'false':
            laws_query = laws_query.filter(is_unique=False)

        if commandment_type in {
            LawOfMessiah.COMMANDMENT_TYPE_POSITIVE,
            LawOfMessiah.COMMANDMENT_TYPE_NEGATIVE,
            LawOfMessiah.COMMANDMENT_TYPE_BOTH,
        }:
            laws_query = laws_query.filter(commandment_type=commandment_type)

        if source_dataset in {LawOfMessiah.SOURCE_DATASET_OT, LawOfMessiah.SOURCE_DATASET_NT}:
            laws_query = laws_query.filter(source_dataset=source_dataset)
        if classical_filter == 'true':
            laws_query = laws_query.filter(classical_commandment=True)
        elif classical_filter == 'false':
            laws_query = laws_query.filter(classical_commandment=False)
        if category:
            laws_query = laws_query.filter(category=category)

        laws = list(laws_query)
        if illustration_filter in {'true', 'false'}:
            wants_illustration = illustration_filter == 'true'
            laws = [law for law in laws if bool(_find_primary_drawing(law)) is wants_illustration]

        if person_code or application_code or ncla_group:
            laws = [law for law in laws if _matches_ncla_filters(law, person_code, application_code, ncla_group)]

        # Language-aware search: include both raw DB text and translated display text (e.g. Dutch UI terms).
        normalized_search = _normalize_search_text(search_query)
        if normalized_search:
            search_terms = [term for term in normalized_search.split() if term]

            def _matches_search(law_obj):
                haystack = [
                    law_obj.id,
                    law_obj.title,
                    law_obj.commandment,
                    law_obj.category,
                    law_obj.translated_title,
                    law_obj.translated_commandment,
                    law_obj.translated_category,
                ]
                searchable_text = ' '.join(_normalize_search_text(item) for item in haystack if item)
                if normalized_search in searchable_text:
                    return True
                if len(search_terms) > 1:
                    return any(term in searchable_text for term in search_terms)
                return False

            laws = [law for law in laws if _matches_search(law)]

        ncla_labels = _ncla_label_map()
        person_labels = _person_label_map()
        for law in laws:
            law.primary_drawing = _find_primary_drawing(law)
            law.primary_drawing_url = _normalize_image_url(law.primary_drawing.img_url) if law.primary_drawing else ''
            law.ncla_human = [ncla_labels.get(code, code) for code in _extract_ncla_codes(law.ncla or [])]
            law.ncla_summary = _ncla_summary(law.ncla or [])
            law.ncla_person_icons = [
                {
                    'code': code,
                    'label': {
                        'JEW': _('Jewish'),
                        'MESSIANIC': _('K\'rov Yisrael'),
                        'GENTILE': _('Gentile'),
                    }.get(code, code)
                }
                for code in _ncla_person_codes(law.ncla or [])
            ]

        filter_options = _ncla_filter_options()
        ncla_group_options = _ncla_group_options(commandment_type=commandment_type, unique_filter=unique_filter)
        category_values = list(
            LawOfMessiah.objects.exclude(category='').order_by('category').values_list('category', flat=True).distinct()
        )
        category_options = [
            {
                'value': value,
                'label': _(value),
            }
            for value in category_values
        ]

        seo_law_index = []
        for law in LawOfMessiah.objects.order_by('id').only('id', 'title'):
            seo_law_index.append(
                {
                    'id': law.id,
                    'title': law.translated_title,
                    'url': reverse('commandments:law_of_messiah_detail', kwargs={'law_id': law.id}),
                }
            )

        return render(
            request,
            'law_of_messiah/listing.html',
            {
                'laws': laws,
                'laws_count': len(laws),
                'selected_q': search_query,
                'selected_source_dataset': source_dataset,
                'selected_commandment_type': commandment_type,
                'selected_is_unique': unique_filter,
                'selected_classical_commandment': classical_filter,
                'selected_illustration': illustration_filter,
                'selected_category': category,
                'selected_ncla_person': person_code,
                'selected_ncla_application': application_code,
                'selected_ncla_group': ncla_group,
                'category_options': category_options,
                'ncla_person_options': filter_options['person'],
                'ncla_application_options': filter_options['application'],
                'ncla_group_options': ncla_group_options,
                'seo_law_index': seo_law_index,
            },
        )


class LawOfMessiahDetailView(View):
    def get(self, request, law_id: str):
        selected_bible = UserPreferences(request.session).bible
        selected_bible_cache_id = str(getattr(selected_bible, 'id', '') or getattr(selected_bible, 'bible_id', '') or selected_bible)
        cached_copyright = cache.get(f"bible_copyright:v1:{selected_bible_cache_id}")
        if cached_copyright:
            selected_bible.copyright = cached_copyright
        law = get_object_or_404(
            LawOfMessiah.objects.prefetch_related('bible_reference_rows', 'media', 'related_steps__drawing_set'),
            pk=law_id,
        )
        if not cached_copyright:
            first_ref = law.bible_reference_rows.first()
            if first_ref is not None:
                try:
                    _reference_text_with_source(first_ref, selected_bible)
                except Exception:
                    pass
        law.primary_drawing = _find_primary_drawing(law)
        law.primary_drawing_url = _normalize_image_url(law.primary_drawing.img_url) if law.primary_drawing else ''
        law.source_is_url = _is_http_url(law.source)

        media_by_type = _filter_grouped_media_by_audience(
            _collect_law_media_by_type(law),
            _allowed_target_audiences(request),
            _allowed_media_languages(request),
        )
        drawings = _dedupe_drawings_for_display(
            media_by_type.get(LawOfMessiahDrawing.MEDIA_TYPE_DRAWING, [])
        )

        related_values = law.related_lawofmessiah or []
        if not related_values:
            related_values = (law.commandments_related_ot or []) + (law.commandments_related_nt or [])
        related_law_ids = _extract_related_law_ids(related_values)
        related_law_map = {
            item.id: item
            for item in LawOfMessiah.objects.filter(id__in=related_law_ids).order_by('id')
        }
        related_steps = list(law.related_steps.all().order_by('id'))

        # Build enriched Maimonides list (deduplicated, with commandment_type + step link)
        unique_mai_ids = list(dict.fromkeys(law.maimonides or []))
        enriched_maimonides = []
        if unique_mai_ids:
            # Build lom_id → [step_ids] from the YAML mapping
            step_to_lom = _step_to_law_mapping()
            lom_to_steps = {}
            for step_id, lom_id in step_to_lom.items():
                lom_to_steps.setdefault(lom_id, []).append(step_id)
            current_law_steps = lom_to_steps.get(law_id, [])

            # Count how many distinct LOM laws reference each Maimonides ID (Python, no DB JSON lookup)
            mai_to_lom_count: dict[str, int] = {}
            for lom_id_iter, mai_list in LawOfMessiah.objects.values_list('id', 'maimonides').exclude(maimonides=[]):
                for mid in set(mai_list or []):
                    mai_to_lom_count[mid] = mai_to_lom_count.get(mid, 0) + 1

            mai_objects = {m.id: m for m in Maimonides.objects.filter(id__in=unique_mai_ids)}
            for mid in unique_mai_ids:
                m_obj = mai_objects.get(mid)
                is_one_to_one = mai_to_lom_count.get(mid, 0) == 1
                enriched_maimonides.append({
                    'id': mid,
                    'commandment': m_obj.commandment if m_obj else mid,
                    'commandment_type': m_obj.commandment_type if m_obj else 'positive',
                    'is_one_to_one': is_one_to_one,
                    'step_ids': current_law_steps if is_one_to_one else [],
                })

        context = {
            'law': law,
            'bible': selected_bible,
            'drawings': drawings,
            'law_media_by_type': media_by_type,
            'related_steps': related_steps,
            'enriched_maimonides': enriched_maimonides,
            'related_lawofmessiah': [related_law_map[item_id] for item_id in related_law_ids if item_id in related_law_map],
            'ncla_human': [_ncla_label_map().get(code, code) for code in _extract_ncla_codes(law.ncla or [])],
            'ncla_summary': _ncla_summary(law.ncla or []),
            'key_nt_scriptures': law.key_nt_scriptures(),
            'key_ot_scriptures': law.key_ot_scriptures(),
            'supportive_nt_scriptures': law.supportive_nt_scriptures(),
            'supportive_ot_scriptures': law.supportive_ot_scriptures(),
        }
        return render(request, 'law_of_messiah/detail.html', context)


class LawOfMessiahBibleVersesView(View):
    """AJAX endpoint: return all verse texts for a Law of Messiah detail page in selected bible."""

    def post(self, request, law_id: str):
        try:
            requested_ref_ids = _requested_ref_ids(request)
            prefs = UserPreferences(request.session)
            bible_id = request.POST.get('bible_id', '')
            if bible_id:
                if not is_bible_id_visible_for_request(request, bible_id):
                    return JsonResponse({'error': 'Bible disabled'}, status=400)
                bible = BibleTranslation().get(bible_id)
                prefs.bible = bible
            else:
                bible = prefs.bible

            law = get_object_or_404(LawOfMessiah.objects.prefetch_related('bible_reference_rows'), pk=law_id)
            verses = {}
            verse_sources = {}
            refs = law.bible_reference_rows.all()
            if requested_ref_ids:
                refs = refs.filter(pk__in=requested_ref_ids)

            for ref in refs:
                text, source = _reference_text_with_source(ref, bible)
                ref_key = str(ref.pk)
                verses[ref_key] = text
                verse_sources[ref_key] = source

            return JsonResponse({'verses': verses, 'verse_sources': verse_sources})
        except Exception as ex:
            logging.getLogger().exception(ex)
            return JsonResponse({'error': 'Could not load Bible verses.'}, status=500)
