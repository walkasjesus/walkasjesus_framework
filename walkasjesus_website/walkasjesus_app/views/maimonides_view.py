import logging
from collections import defaultdict
import re

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views import View

from walkasjesus_app.lib.access_policy import is_bible_id_visible_for_request
from walkasjesus_app.models import BibleTranslation, LawOfMessiah, Maimonides, MaimonidesBibleReference, UserPreferences


VERSE_CACHE_TIMEOUT = int(getattr(settings, 'BIBLE_API_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))


def _build_lom_by_maimonides_id():
    """Return a dict mapping each Maimonides ID to the LOM objects that reference it."""
    lom_rows = (
        LawOfMessiah.objects
        .exclude(maimonides=[])
        .only('id', 'title', 'commandment_type', 'maimonides')
    )
    lom_by_mai = defaultdict(list)
    # Index LOM objects by id so we attach the full object
    lom_map = {lom.id: lom for lom in lom_rows}
    for lom in lom_rows:
        for mai_id in lom.maimonides or []:
            lom_by_mai[str(mai_id)].append(lom_map[lom.id])
    return lom_by_mai


def _natural_code_key(value):
    text = str(value or '').strip()
    match = re.match(r'^([A-Za-z]+)(\d+)$', text)
    if match:
        prefix, number = match.groups()
        return prefix, int(number)
    return text, 0


def _first_code_key(values):
    if not values:
        return ('ZZZ', 10**9)
    return _natural_code_key(values[0])


def _scripture_detail_lines(details):
    lines = []
    for item in details or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get('id', '')).strip()
        scriptures = [str(scripture).strip() for scripture in item.get('scriptures', []) if str(scripture).strip()]
        if item_id and scriptures:
            lines.append(f"{item_id}: {', '.join(scriptures)}")
    return lines


def _reference_signature(ref):
    return (ref.book, ref.begin_chapter, ref.begin_verse, ref.end_chapter, ref.end_verse)


def _source_type_label(reference_type):
    mapping = {
        MaimonidesBibleReference.TYPE_MAIMONIDES: _('Maimonides'),
        MaimonidesBibleReference.TYPE_MEIR: _('Meir'),
        MaimonidesBibleReference.TYPE_CHINUCH: _('HaChinuch'),
    }
    return mapping.get(reference_type, reference_type)


def _shared_scripture_usage_title(reference_types):
    ordered = [
        MaimonidesBibleReference.TYPE_MAIMONIDES,
        MaimonidesBibleReference.TYPE_MEIR,
        MaimonidesBibleReference.TYPE_CHINUCH,
    ]
    labels = [_source_type_label(reference_type) for reference_type in ordered if reference_type in reference_types]
    if not labels:
        return ''
    if len(labels) == 1:
        return _('Scripture used by %(source)s') % {'source': labels[0]}
    if len(labels) == 2:
        return _('Scripture used by %(first)s and %(second)s') % {'first': labels[0], 'second': labels[1]}
    return _('Scripture used by %(first)s, %(second)s and %(third)s') % {
        'first': labels[0],
        'second': labels[1],
        'third': labels[2],
    }


def _scripture_entries(rows):
    grouped = {}
    for row in rows:
        signature = _reference_signature(row)
        if signature not in grouped:
            grouped[signature] = {
                'reference': row,
                'reference_types': set(),
                'source_codes': set(),
            }
        grouped[signature]['reference_types'].add(row.reference_type)
        if row.source_code:
            grouped[signature]['source_codes'].add(str(row.source_code).strip())

    entries = []
    for item in grouped.values():
        reference_types = item['reference_types']
        source_codes = sorted(item['source_codes'], key=_natural_code_key)
        source_type_labels = sorted({_source_type_label(reference_type) for reference_type in reference_types})
        entries.append({
            'reference': item['reference'],
            'usage_title': _shared_scripture_usage_title(reference_types),
            'source_codes': source_codes,
            'source_codes_text': ', '.join(source_codes),
            'source_type_labels': source_type_labels,
        })

    entries.sort(key=lambda item: (
        item['reference'].begin_chapter,
        item['reference'].begin_verse,
        item['reference'].end_chapter,
        item['reference'].end_verse,
        item['reference'].display_reference(),
    ))
    return entries


def _reference_text_with_source(ref, bible):
    bible_cache_id = str(getattr(bible, 'id', '') or getattr(bible, 'bible_id', '') or bible)
    copyright_cache_key = f'bible_copyright:v1:{bible_cache_id}'
    cache_key = (
        f'verse_text:v1:{bible_cache_id}:'
        f'{ref.book}:{ref.begin_chapter}:{ref.begin_verse}:{ref.end_chapter}:{ref.end_verse}'
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


def _requested_ref_ids(request):
    requested = []
    requested.extend(request.POST.getlist('verse_refs[]'))
    requested.extend(request.POST.getlist('verse_refs'))

    single = request.POST.get('verse_refs', '')
    if single and ',' in single:
        requested.extend(single.split(','))

    return {str(item).strip() for item in requested if str(item).strip()}


def _commandment_search_blob(cmd):
    parts = [cmd.id, cmd.commandment]
    parts.extend(cmd.meir or [])
    parts.extend(cmd.chinuch or [])
    parts.extend(cmd.rudolph or [])
    parts.extend(cmd.scriptures or [])
    parts.extend(_scripture_detail_lines(cmd.meir_scriptures))
    parts.extend(_scripture_detail_lines(cmd.chinuch_scriptures))
    for ref in getattr(cmd, 'prefetched_bible_reference_rows', []):
        parts.append(ref.display_reference())
        parts.append(ref.source_code)
        parts.append(ref.get_reference_type_display())
    parts.extend(lom.id for lom in getattr(cmd, 'related_lawofmessiah', []))
    parts.extend(lom.title for lom in getattr(cmd, 'related_lawofmessiah', []) if lom.title)
    return ' '.join(str(part or '') for part in parts).lower()


SORT_OPTIONS = [
    ('maimonides_id', 'Maimonides ID'),
    ('commandment', 'Commandment text'),
    ('type', 'Type'),
    ('meir', 'Meir of Rothenburg'),
    ('chinuch', 'Sefer HaChinuch'),
    ('related', 'Related Law of Messiah count'),
]


class MaimonidesList(View):
    def get(self, request):
        search_query = request.GET.get('q', '').strip()
        type_filter = request.GET.get('commandment_type', '').strip().lower()
        sort_by = request.GET.get('sort', 'maimonides_id').strip()
        selected_bible = UserPreferences(request.session).bible

        commandments = list(Maimonides.objects.prefetch_related('bible_reference_rows'))
        lom_by_mai = _build_lom_by_maimonides_id()

        for cmd in commandments:
            # Attach related LOM objects, de-duplicated by id
            seen = set()
            related = []
            for lom in lom_by_mai.get(cmd.id, []):
                if lom.id not in seen:
                    seen.add(lom.id)
                    related.append(lom)
            cmd.related_lawofmessiah = related
            cmd.related_lawofmessiah_count = len(related)
            cmd.prefetched_bible_reference_rows = list(cmd.bible_reference_rows.all())
            cmd.meir_scripture_lines = _scripture_detail_lines(cmd.meir_scriptures)
            cmd.chinuch_scripture_lines = _scripture_detail_lines(cmd.chinuch_scriptures)
            cmd.scripture_entries = _scripture_entries(cmd.prefetched_bible_reference_rows)

        if type_filter in {Maimonides.COMMANDMENT_TYPE_POSITIVE, Maimonides.COMMANDMENT_TYPE_NEGATIVE}:
            commandments = [cmd for cmd in commandments if cmd.commandment_type == type_filter]

        if search_query:
            query = search_query.lower()
            commandments = [cmd for cmd in commandments if query in _commandment_search_blob(cmd)]

        if sort_by == 'commandment':
            commandments.sort(key=lambda cmd: (str(cmd.commandment or '').lower(), _natural_code_key(cmd.id)))
        elif sort_by == 'type':
            commandments.sort(key=lambda cmd: (str(cmd.commandment_type or '').lower(), _natural_code_key(cmd.id)))
        elif sort_by == 'meir':
            commandments.sort(key=lambda cmd: (_first_code_key(cmd.meir), _natural_code_key(cmd.id)))
        elif sort_by == 'chinuch':
            commandments.sort(key=lambda cmd: (_first_code_key(cmd.chinuch), _natural_code_key(cmd.id)))
        elif sort_by == 'related':
            commandments.sort(key=lambda cmd: (-cmd.related_lawofmessiah_count, _natural_code_key(cmd.id)))
        else:
            sort_by = 'maimonides_id'
            commandments.sort(key=lambda cmd: _natural_code_key(cmd.id))

        return render(request, 'maimonides/listing.html', {
            'commandments': commandments,
            'commandments_count': len(commandments),
            'selected_q': search_query,
            'selected_commandment_type': type_filter,
            'selected_sort': sort_by,
            'sort_options': SORT_OPTIONS,
            'bible': selected_bible,
        })


class MaimonidesBibleVersesView(View):
    def post(self, request, maimonides_id: str):
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

            commandment = get_object_or_404(Maimonides.objects.prefetch_related('bible_reference_rows'), pk=maimonides_id)
            verses = {}
            verse_sources = {}

            for ref in commandment.bible_reference_rows.all():
                ref_key = str(ref.pk)
                if requested_ref_ids and ref_key not in requested_ref_ids:
                    continue
                text, source = _reference_text_with_source(ref, bible)
                verses[ref_key] = text
                verse_sources[ref_key] = source

            return JsonResponse({'verses': verses, 'verse_sources': verse_sources})
        except Exception as ex:
            logging.getLogger().exception(ex)
            return JsonResponse({'error': 'Could not load Bible verses.'}, status=500)
