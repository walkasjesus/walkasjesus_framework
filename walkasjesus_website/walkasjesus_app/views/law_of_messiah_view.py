import logging
import re
from urllib.parse import urlparse

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views import View

from walkasjesus_app.models import BibleTranslation, LawOfMessiah, Maimonides, UserPreferences
from walkasjesus_app.views.detail_view import _step_to_law_mapping


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
    for drawing in law.media.all():
        if drawing.img_url:
            return drawing
    return None


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
            'groups': [],
        }

    person_labels = _person_label_map()
    application_labels = _application_label_map()
    groups_detail = []
    all_person_codes = set()
    all_application_codes = set()

    for entry in ncla_data:
        if not isinstance(entry, dict):
            continue
        group_name = entry.get('group', 'All')
        codes = entry.get('codes', [])
        detailed = []
        for code in codes:
            if len(code) >= 3:
                person_code = code[:2]
                application_code = code[-1]
                person_label = person_labels.get(person_code, person_code)
                application_label = application_labels.get(application_code, application_code)
                detailed.append(f'{code} - {person_label}, {application_label}')
            else:
                detailed.append(code)
        person_set = sorted(set(c[:2] for c in codes if len(c) >= 3))
        app_set = sorted(set(c[-1] for c in codes if len(c) >= 3))
        all_person_codes.update(person_set)
        all_application_codes.update(app_set)
        groups_detail.append({
            'group': group_name,
            'codes': codes,
            'detailed': detailed,
            'person_summary': ', '.join(person_labels.get(p, p) for p in person_set),
            'application_summary': ', '.join(application_labels.get(a, a) for a in app_set),
        })

    unique_persons = sorted(all_person_codes)
    unique_applications = sorted(all_application_codes)

    if set(unique_persons) == set(person_labels.keys()):
        person_categories = _('Everyone')
    else:
        person_categories = ', '.join(person_labels.get(p, p) for p in unique_persons)

    literal_application = ', '.join(application_labels.get(a, a) for a in unique_applications)

    return {
        'person_categories': person_categories,
        'literal_application': literal_application,
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


def _ncla_group_options():
    """Return distinct ncla group names from laws that have ncla_deviation, for the context filter."""
    groups = set()
    for ncla_data in LawOfMessiah.objects.filter(ncla_deviation=True).values_list('ncla', flat=True):
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
    cache_key = (
        f"verse_text:v1:{getattr(bible, 'id', '') or getattr(bible, 'bible_id', '') or bible}:"
        f"{ref.book}:{ref.begin_chapter}:{ref.begin_verse}:{ref.end_chapter}:{ref.end_verse}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, 'cache'

    end_chapter = ref.end_chapter if ref.end_chapter else ref.begin_chapter
    end_verse = ref.end_verse if ref.end_verse else ref.begin_verse
    text = bible.verses(BibleLibBibleBooks[ref.book], ref.begin_chapter, ref.begin_verse, end_chapter, end_verse)
    cache.set(cache_key, text, VERSE_CACHE_TIMEOUT)
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


class LawOfMessiahListingView(View):
    def get(self, request):
        search_query = request.GET.get('q', '').strip()
        source_dataset = request.GET.get('source_dataset', '').strip().lower()
        commandment_type = request.GET.get('commandment_type', '').strip().lower()
        classical_filter = request.GET.get('classical_commandment', '').strip().lower()
        category = request.GET.get('category', '').strip()
        person_code = request.GET.get('ncla_person', '').strip().upper()
        application_code = request.GET.get('ncla_application', '').strip().lower()
        ncla_group = request.GET.get('ncla_group', '').strip()

        laws_query = LawOfMessiah.objects.filter(
            is_unique=True, commandment_type=LawOfMessiah.COMMANDMENT_TYPE_POSITIVE
        ).order_by('id').prefetch_related('media')
        if search_query:
            laws_query = laws_query.filter(
                Q(id__icontains=search_query)
                | Q(title__icontains=search_query)
                | Q(commandment__icontains=search_query)
            )
        if source_dataset in {LawOfMessiah.SOURCE_DATASET_OT, LawOfMessiah.SOURCE_DATASET_NT}:
            laws_query = laws_query.filter(source_dataset=source_dataset)
        if classical_filter == 'true':
            laws_query = laws_query.filter(classical_commandment=True)
        elif classical_filter == 'false':
            laws_query = laws_query.filter(classical_commandment=False)
        if category:
            laws_query = laws_query.filter(category=category)

        laws = list(laws_query)
        if person_code or application_code or ncla_group:
            laws = [law for law in laws if _matches_ncla_filters(law, person_code, application_code, ncla_group)]

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
        ncla_group_options = _ncla_group_options()
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
        return render(
            request,
            'law_of_messiah/listing.html',
            {
                'laws': laws,
                'laws_count': len(laws),
                'selected_q': search_query,
                'selected_source_dataset': source_dataset,
                'selected_commandment_type': commandment_type,
                'selected_classical_commandment': classical_filter,
                'selected_category': category,
                'selected_ncla_person': person_code,
                'selected_ncla_application': application_code,
                'selected_ncla_group': ncla_group,
                'category_options': category_options,
                'ncla_person_options': filter_options['person'],
                'ncla_application_options': filter_options['application'],
                'ncla_group_options': ncla_group_options,
            },
        )


class LawOfMessiahDetailView(View):
    def get(self, request, law_id: str):
        selected_bible = UserPreferences(request.session).bible
        law = get_object_or_404(
            LawOfMessiah.objects.prefetch_related('bible_reference_rows', 'media', 'related_steps__drawing_set'),
            pk=law_id,
        )
        law.primary_drawing = _find_primary_drawing(law)
        law.primary_drawing_url = _normalize_image_url(law.primary_drawing.img_url) if law.primary_drawing else ''
        law.source_is_url = _is_http_url(law.source)

        drawings = []
        for drawing in law.media.all():
            drawings.append({
                'author': drawing.author,
                'description': drawing.description,
                'img_url': _normalize_image_url(drawing.img_url),
            })

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
                if bible_id in settings.DISABLED_BIBLE_TRANSLATIONS:
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
