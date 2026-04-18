import logging

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views import View

from walkasjesus_app.models import BibleTranslation, LawOfMessiah, UserPreferences


def _normalize_image_url(url):
    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://') or url.startswith('/'):
        return url
    return '/' + url


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


def _ncla_summary(values):
    if not values:
        return {
            'person_categories': _('Not specified'),
            'literal_application': _('Not specified'),
            'detailed_codes': [],
        }

    person_labels = _person_label_map()
    application_labels = _application_label_map()
    person_codes = []
    application_codes = []
    for code in values:
        if len(code) < 3:
            continue
        person_codes.append(code[:2])
        application_codes.append(code[-1])

    unique_persons = sorted(set(person_codes))
    unique_applications = sorted(set(application_codes))
    if set(unique_persons) == set(person_labels.keys()):
        person_categories = _('Everyone')
    else:
        person_categories = ', '.join(person_labels.get(code, code) for code in unique_persons)

    literal_application = ', '.join(application_labels.get(code, code) for code in unique_applications)
    detailed_codes = [_ncla_label_map().get(code, code) for code in values]
    return {
        'person_categories': person_categories,
        'literal_application': literal_application,
        'detailed_codes': detailed_codes,
    }


def _matches_ncla_filters(law, person_code, application_code):
    values = law.ncla or []
    if not values:
        return not person_code and not application_code

    for code in values:
        if person_code and not code.startswith(person_code):
            continue
        if application_code and not code.endswith(application_code):
            continue
        return True
    return False


def _reference_text(ref, bible):
    end_chapter = ref.end_chapter if ref.end_chapter else ref.begin_chapter
    end_verse = ref.end_verse if ref.end_verse else ref.begin_verse
    return bible.verses(BibleLibBibleBooks[ref.book], ref.begin_chapter, ref.begin_verse, end_chapter, end_verse)


class LawOfMessiahListingView(View):
    def get(self, request):
        source_dataset = request.GET.get('source_dataset', '').strip().lower()
        commandment_type = request.GET.get('commandment_type', '').strip().lower()
        commandment_form = request.GET.get('commandment_form', '').strip().lower()
        category = request.GET.get('category', '').strip()
        person_code = request.GET.get('ncla_person', '').strip().upper()
        application_code = request.GET.get('ncla_application', '').strip().lower()

        laws_query = LawOfMessiah.objects.order_by('id').prefetch_related('media')
        if source_dataset in {LawOfMessiah.SOURCE_DATASET_OT, LawOfMessiah.SOURCE_DATASET_NT}:
            laws_query = laws_query.filter(source_dataset=source_dataset)
        if commandment_type in {
            LawOfMessiah.COMMANDMENT_TYPE_POSITIVE,
            LawOfMessiah.COMMANDMENT_TYPE_NEGATIVE,
            LawOfMessiah.COMMANDMENT_TYPE_BOTH,
        }:
            laws_query = laws_query.filter(commandment_type=commandment_type)
        if commandment_form in {
            LawOfMessiah.COMMANDMENT_FORM_EXPLICIT,
            LawOfMessiah.COMMANDMENT_FORM_IMPLIED,
        }:
            laws_query = laws_query.filter(commandment_form=commandment_form)
        if category:
            laws_query = laws_query.filter(category=category)

        laws = list(laws_query)
        if person_code or application_code:
            laws = [law for law in laws if _matches_ncla_filters(law, person_code, application_code)]

        ncla_labels = _ncla_label_map()
        for law in laws:
            law.primary_drawing = _find_primary_drawing(law)
            law.primary_drawing_url = _normalize_image_url(law.primary_drawing.img_url) if law.primary_drawing else ''
            law.ncla_human = [ncla_labels.get(code, code) for code in (law.ncla or [])]
            law.ncla_summary = _ncla_summary(law.ncla or [])

        filter_options = _ncla_filter_options()
        categories = list(
            LawOfMessiah.objects.exclude(category='').order_by('category').values_list('category', flat=True).distinct()
        )
        return render(
            request,
            'law_of_messiah/listing.html',
            {
                'laws': laws,
                'laws_count': len(laws),
                'selected_source_dataset': source_dataset,
                'selected_commandment_type': commandment_type,
                'selected_commandment_form': commandment_form,
                'selected_category': category,
                'selected_ncla_person': person_code,
                'selected_ncla_application': application_code,
                'category_options': categories,
                'ncla_person_options': filter_options['person'],
                'ncla_application_options': filter_options['application'],
            },
        )


class LawOfMessiahDetailView(View):
    def get(self, request, law_id: str):
        law = get_object_or_404(LawOfMessiah.objects.prefetch_related('bible_reference_rows', 'media'), pk=law_id)
        law.primary_drawing = _find_primary_drawing(law)
        law.primary_drawing_url = _normalize_image_url(law.primary_drawing.img_url) if law.primary_drawing else ''

        drawings = []
        for drawing in law.media.all():
            drawings.append({
                'author': drawing.author,
                'description': drawing.description,
                'img_url': _normalize_image_url(drawing.img_url),
            })

        context = {
            'law': law,
            'drawings': drawings,
            'ncla_human': [_ncla_label_map().get(code, code) for code in (law.ncla or [])],
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
            for ref in law.bible_reference_rows.all():
                verses[str(ref.pk)] = _reference_text(ref, bible)

            return JsonResponse({'verses': verses})
        except Exception as ex:
            logging.getLogger().exception(ex)
            return JsonResponse({'error': 'Could not load Bible verses.'}, status=500)
