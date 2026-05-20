import csv
from pathlib import Path

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.admin.widgets import FilteredSelectMultiple
from django import forms
from django.urls import path, reverse
from django.utils.html import escape, mark_safe
from reversion.admin import VersionAdmin
from django.db.models import Count, Q

from walkasjesus_app.models import *
from walkasjesus_app.models.commandment_question import Question
from walkasjesus_app.models.lesson_question import LessonQuestion
from walkasjesus_app.models.lesson_media import *
from walkasjesus_app.views.admin.admin_bible_view import AdminBibleView
from walkasjesus_website.settings import BASE_DIR


class Bible(models.Model):
    class Meta:
        managed = False
        verbose_name_plural = 'Bible'
        app_label = 'commandments_app'


class BibleAdmin(admin.ModelAdmin):
    model = Bible

    def get_urls(self):
        view_name = '{}_{}_changelist'.format(self.model._meta.app_label, self.model._meta.model_name)
        return [
            path('', AdminBibleView.as_view(), name=view_name),
        ]

class MediaTargetAudienceFilter(SimpleListFilter):
    title = 'media target audience'
    parameter_name = 'media_target_audience'

    def lookups(self, request, model_admin):
        audiences = set()
        for model in [Song, Movie, Superbook, Henkieshow, ShortMovie, WaJVideo, Drawing, Testimony, Blog, Picture, Sermon, Book]:
            audiences.update(model.objects.values_list('target_audience', flat=True))
        return [(a, a) for a in audiences if a]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        from django.db.models import Q
        q = Q()
        for rel in [
            'song', 'movie', 'superbook', 'henkieshow', 'shortmovie', 'wajvideo',
            'drawing', 'testimony', 'blog', 'picture', 'sermon', 'book'
        ]:
            q |= Q(**{f"{rel}__target_audience": value})
        return queryset.filter(q).distinct()

class MediaLanguageFilter(SimpleListFilter):
    title = 'media language'
    parameter_name = 'media_language'

    def lookups(self, request, model_admin):
        languages = set()
        for model in [Song, Movie, Superbook, Henkieshow, ShortMovie, WaJVideo, Drawing, Testimony, Blog, Picture, Sermon, Book]:
            languages.update(model.objects.values_list('language', flat=True))
        return [(l, l) for l in languages if l]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        from django.db.models import Q
        q = Q()
        for rel in [
            'song', 'movie', 'superbook', 'henkieshow', 'shortmovie', 'wajvideo',
            'drawing', 'testimony', 'blog', 'picture', 'sermon', 'book'
        ]:
            q |= Q(**{f"{rel}__language": value})
        return queryset.filter(q).distinct()

class PrimaryBibleReferencesInline(admin.TabularInline):
    model = PrimaryBibleReference
    extra = 0

class DirectBibleReferenceInline(admin.TabularInline):
    model = DirectBibleReference
    extra = 0

class IndirectBibleReferenceInline(admin.TabularInline):
    model = IndirectBibleReference
    extra = 0


class DuplicateBibleReferenceInline(admin.TabularInline):
    model = DuplicateBibleReference
    extra = 0


class ExampleBibleReferenceInline(admin.TabularInline):
    model = ExampleBibleReference
    extra = 0


class StudyBibleReferenceInline(admin.TabularInline):
    model = StudyBibleReference
    extra = 0

class OTLawBibleReferenceInline(admin.TabularInline):
    model = OTLawBibleReference
    extra = 0


class WisdomBibleReferenceInline(admin.TabularInline):
    model = WisdomBibleReference
    extra = 0


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


class DrawingInline(admin.TabularInline):
    model = Drawing
    extra = 0


class SongInline(admin.TabularInline):
    model = Song
    extra = 0

class SuperbookInline(admin.TabularInline):
    model = Superbook
    extra = 0

class HenkieshowInline(admin.TabularInline):
    model = Henkieshow
    extra = 0

class MovieInline(admin.TabularInline):
    model = Movie
    extra = 0


class ShortMovieInline(admin.TabularInline):
    model = ShortMovie
    extra = 0


class WaJVideoInline(admin.TabularInline):
    model = WaJVideo
    extra = 0


class SermonInline(admin.TabularInline):
    model = Sermon
    extra = 0

class PictureInline(admin.TabularInline):
    model = Picture
    extra = 0

class TestimonyInline(admin.TabularInline):
    model = Testimony
    extra = 0

class BlogInline(admin.TabularInline):
    model = Blog
    extra = 0


class BookInline(admin.TabularInline):
    model = Book
    extra = 0


def commandment_category_choices(current_value=''):
    categories = []
    seen = set()
    csv_path = Path(BASE_DIR) / 'data' / 'biblereferences' / 'commandments.csv'

    try:
        with open(csv_path, 'r', encoding='utf-8', newline='') as handle:
            reader = csv.DictReader(handle, delimiter=';')
            for row in reader:
                category = (row.get('category') or '').strip()
                if category and category not in seen:
                    seen.add(category)
                    categories.append(category)
    except FileNotFoundError:
        pass

    for category in Commandment.objects.exclude(category='').order_by('category').values_list('category', flat=True).distinct():
        if category not in seen:
            seen.add(category)
            categories.append(category)

    if current_value and current_value not in seen:
        categories.append(current_value)

    return [(category, category) for category in categories]


class CommandmentAdminForm(forms.ModelForm):
    class Meta:
        model = Commandment
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_value = getattr(self.instance, 'category', '') if self.instance else ''
        self.fields['category'] = forms.ChoiceField(
            choices=commandment_category_choices(current_value=current_value),
            required=False,
        )


class CommandmentAdmin(VersionAdmin):
    form = CommandmentAdminForm

    class Meta:
        verbose_name_plural = 'Step'

    list_display = [
        'id',
        'title',
        'category',
        'quote',
        'song_count',
        'shortmovie_count',
        'testimony_count',
        'sermon_count',
        'movie_count',
        'blog_count',
        'superbook_count',
        'henkieshow_count',        
    ]
    list_filter = ['category', MediaTargetAudienceFilter, MediaLanguageFilter]
    search_fields = ['=id', 'title', 'quote']
    inlines = [
        PrimaryBibleReferencesInline,
        DirectBibleReferenceInline,
        IndirectBibleReferenceInline,
        ExampleBibleReferenceInline,
        DuplicateBibleReferenceInline,
        StudyBibleReferenceInline,
        OTLawBibleReferenceInline,
        WisdomBibleReferenceInline,
        QuestionInline,
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Get filter values from request.GET
        target_audience = request.GET.get('media_target_audience')
        media_language = request.GET.get('media_language')

        # Annotate counts based on filters
        song_filter = Q()
        movie_filter = Q()
        shortmovie_filter = Q()
        testimony_filter = Q()
        blog_filter = Q()
        sermon_filter = Q()
        superbook_filter = Q()
        henkieshow_filter = Q()
        if target_audience:
            song_filter &= Q(song__target_audience=target_audience)
            movie_filter &= Q(movie__target_audience=target_audience)
            shortmovie_filter &= Q(shortmovie__target_audience=target_audience)
            testimony_filter &= Q(testimony__target_audience=target_audience)
            blog_filter &= Q(blog__target_audience=target_audience)
            sermon_filter &= Q(sermon__target_audience=target_audience)
            superbook_filter &= Q(superbook__target_audience=target_audience)
            henkieshow_filter &= Q(henkieshow__target_audience=target_audience)
        if media_language:
            song_filter &= Q(song__language=media_language)
            movie_filter &= Q(movie__language=media_language)
            shortmovie_filter &= Q(shortmovie__language=media_language)
            testimony_filter &= Q(testimony__language=media_language)
            blog_filter &= Q(blog__language=media_language)
            sermon_filter &= Q(sermon__language=media_language)
            superbook_filter &= Q(superbook__language=media_language)
            henkieshow_filter &= Q(henkieshow__language=media_language)

        return qs.annotate(
            song_count=Count('song', filter=song_filter, distinct=True),
            movie_count=Count('movie', filter=movie_filter, distinct=True),
            shortmovie_count=Count('shortmovie', filter=shortmovie_filter, distinct=True),
            testimony_count=Count('testimony', filter=testimony_filter, distinct=True),
            blog_count=Count('blog', filter=blog_filter, distinct=True),
            sermon_count=Count('sermon', filter=sermon_filter, distinct=True),
            superbook_count=Count('superbook', filter=superbook_filter, distinct=True),
            henkieshow_count=Count('henkieshow', filter=henkieshow_filter, distinct=True),
        )
    
    def song_count(self, obj):
        return obj.song_count
    song_count.admin_order_field = 'song_count'
    song_count.short_description = "Songs"

    def movie_count(self, obj):
        return obj.movie_count
    movie_count.admin_order_field = 'movie_count'
    movie_count.short_description = "Movies"

    def shortmovie_count(self, obj):
        return obj.shortmovie_count
    shortmovie_count.admin_order_field = 'shortmovie_count'
    shortmovie_count.short_description = "ShortMovies"

    def testimony_count(self, obj):
        return obj.testimony_count
    testimony_count.admin_order_field = "testimony_count"
    testimony_count.short_description = "Testimonies"

    def blog_count(self, obj):
        return obj.blog_count
    blog_count.admin_order_field = "blog_count"
    blog_count.short_description = "Blogs"

    def sermon_count(self, obj):
        return obj.sermon_count
    sermon_count.admin_order_field = "sermon_count"
    sermon_count.short_description = "Sermons"

    def superbook_count(self, obj):
        return obj.superbook_count
    superbook_count.admin_order_field = 'superbook_count'
    superbook_count.short_description = "Superbooks"

    def henkieshow_count(self, obj):
        return obj.henkieshow_count
    henkieshow_count.admin_order_field = 'henkieshow_count'
    henkieshow_count.short_description = "Henkieshows"

class PrimaryLessonBibleReferencesInline(admin.TabularInline):
    model = PrimaryLessonBibleReference
    extra = 0
    "We don't use these fields within lessons"
    exclude = ('ot_nr', 'ot_rambam_id', 'ot_rambam_title', 'author')

class DirectLessonBibleReferenceInline(admin.TabularInline):
    model = DirectLessonBibleReference
    extra = 0
    "We don't use these fields within lessons"
    exclude = ('ot_nr', 'ot_rambam_id', 'ot_rambam_title', 'author')

class LessonBibleSectionInLine(admin.TabularInline):
    model = LessonBibleSection
    extra = 0
    "We don't use these fields within lessons"
    exclude = ('ot_nr', 'ot_rambam_id', 'ot_rambam_title', 'author', 'positive_negative')

class LessonDrawingInline(admin.TabularInline):
    model = LessonDrawing
    extra = 0


class LessonSongInline(admin.TabularInline):
    model = LessonSong
    extra = 0
    "We don't use these fields within lessons"
    exclude = ('img_url',)

class LessonSuperbookInline(admin.TabularInline):
    model = LessonSuperbook
    extra = 0
    "We don't use these fields within lessons"
    exclude = ('img_url',)

class LessonHenkieshowInline(admin.TabularInline):
    model = LessonHenkieshow
    extra = 0
    "We don't use these fields within lessons"
    exclude = ('img_url',)

class LessonShortMovieInline(admin.TabularInline):
    model = LessonShortMovie
    extra = 0
    "We don't use these fields within lessons"
    exclude = ('img_url',)

class LessonPictureInline(admin.TabularInline):
    model = LessonPicture
    extra = 0

class LessonTestimonyInline(admin.TabularInline):
    model = LessonTestimony
    extra = 0
    "We don't use these fields within lessons"
    exclude = ('img_url',)

class LessonQuestionInline(admin.TabularInline):
    model = LessonQuestion
    extra = 0

class LessonAdmin(VersionAdmin):
    list_display = ['id', 'story', 'bible_section', 'title']
    search_fields = ['=id', 'title', 'story', 'commandment__title']
    inlines = [
        LessonQuestionInline,
        LessonBibleSectionInLine,
        PrimaryLessonBibleReferencesInline,
        DirectLessonBibleReferenceInline,
    ]


class LawOfMessiahBibleReferenceInline(admin.TabularInline):
    model = LawOfMessiahBibleReference
    extra = 0
    fields = ['reference_type', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse']


class LawOfMessiahDrawingInline(admin.TabularInline):
    model = LawOfMessiahDrawing
    extra = 1
    fields = ['media_type', 'author', 'title', 'description', 'img_url', 'url', 'target_audience', 'language', 'is_public']


class NCLAGroupWidget(forms.Widget):
    """Compact checkbox-grid widget for editing structured NCLA groups."""

    PERSON_CODES = ['JM', 'JF', 'KM', 'KF', 'GM', 'GF']
    PERSON_LABELS = {
        'JM': 'Jewish M', 'JF': 'Jewish F',
        'KM': "K'rov M", 'KF': "K'rov F",
        'GM': 'Gentile M', 'GF': 'Gentile F',
    }
    APP_CODES = ['m', 'r', 'o', 'n', 'u', 'p', 'i']
    APP_LABELS = {
        'm': 'Mand.', 'r': 'Recomm.', 'o': 'Optional',
        'n': 'Not recom.', 'u': 'Unauthor.', 'p': 'Prohib.', 'i': 'Imposs.',
    }
    APP_COLORS = {
        'm': '#c8e6c9', 'r': '#dcedc8', 'o': '#fff9c4',
        'n': '#ffe0b2', 'u': '#ffccbc', 'p': '#ffcdd2', 'i': '#e0e0e0',
    }

    def format_value(self, value):
        import json as _json
        if not value:
            return [{'group': 'All', 'codes': []}]
        if isinstance(value, str):
            try:
                parsed = _json.loads(value)
                if isinstance(parsed, list):
                    if parsed and isinstance(parsed[0], str):
                        return [{'group': 'All', 'codes': sorted(parsed)}]
                    return parsed or [{'group': 'All', 'codes': []}]
            except Exception:
                pass
            return [{'group': 'All', 'codes': []}]
        if isinstance(value, list):
            if not value:
                return [{'group': 'All', 'codes': []}]
            if isinstance(value[0], str):
                return [{'group': 'All', 'codes': sorted(value)}]
            return value
        return [{'group': 'All', 'codes': []}]

    def value_from_datadict(self, data, files, name):
        return data.get(name, '')

    def render(self, name, value, attrs=None, renderer=None):
        import json as _json
        groups = self.format_value(value)
        widget_id = (attrs or {}).get('id', name)
        json_attr = escape(_json.dumps(groups, ensure_ascii=False))

        parts = []
        parts.append(f'<div class="ncla-widget" id="ncla-widget-{widget_id}">')
        parts.append(f'<input type="hidden" name="{name}" id="{widget_id}" value="{json_attr}">')
        # Hidden template for JS cloning
        parts.append('<div style="display:none">')
        parts.append(self._group_html('__TPL__', 'New Group', [], widget_id, template=True))
        parts.append('</div>')
        parts.append(f'<div id="ncla-groups-{widget_id}">')
        for i, grp in enumerate(groups):
            parts.append(self._group_html(i, grp.get('group', 'All'), grp.get('codes', []), widget_id))
        parts.append('</div>')
        parts.append(f'<button type="button" class="button" style="margin-top:6px" onclick="nclaAddGroup(\'{widget_id}\')">')
        parts.append('+ Add group</button>')
        parts.append('</div>')
        parts.append(self._js(widget_id))
        return mark_safe('\n'.join(parts))

    def _group_html(self, index, group_name, codes, widget_id, template=False):
        tmpl = ' data-template="1"' if template else ''
        code_set = set(codes)
        safe_name = escape(group_name)
        rows = []
        rows.append(
            f'<div class="ncla-group-block" data-index="{index}"{tmpl} '
            f'style="margin:6px 0;padding:8px;border:1px solid #ccc;background:#f9f9f9">'
        )
        rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
            f'<strong>Group:</strong>'
            f'<input type="text" class="ncla-gname" value="{safe_name}" style="flex:1;padding:2px 6px" '
            f'onchange="nclaSerialize(\'{widget_id}\')">'
            f'<button type="button" class="button" style="background:#ba2121;color:#fff;padding:2px 8px" '
            f'onclick="nclaRemove(this,\'{widget_id}\')">&#x2715; Remove</button>'
            f'</div>'
        )
        rows.append('<table style="border-collapse:collapse;font-size:11px">')
        rows.append('<tr><th style="padding:3px 8px;text-align:left">Person</th>')
        for ac in self.APP_CODES:
            bg = self.APP_COLORS.get(ac, '')
            rows.append(f'<th style="padding:3px 5px;text-align:center;background:{bg}">{self.APP_LABELS[ac]}<br><code>{ac}</code></th>')
        rows.append('</tr>')
        for pc in self.PERSON_CODES:
            rows.append(f'<tr><td style="padding:3px 8px;font-weight:bold">{self.PERSON_LABELS[pc]}<br><code style="font-weight:normal">{pc}</code></td>')
            for ac in self.APP_CODES:
                full_code = f'{pc}{ac}'
                chk = ' checked' if full_code in code_set else ''
                bg = self.APP_COLORS.get(ac, '')
                rows.append(
                    f'<td style="text-align:center;background:{bg}">'
                    f'<input type="checkbox" class="ncla-cb" data-code="{full_code}"{chk} '
                    f'onchange="nclaSerialize(\'{widget_id}\')" title="{full_code}">'
                    f'</td>'
                )
            rows.append('</tr>')
        rows.append('</table></div>')
        return '\n'.join(rows)

    def _js(self, wid):
        return (
            f'<script>(function(){{'
            f'function ser(wid){{'
            f'var g=[];'
            f'document.querySelectorAll("#ncla-groups-"+wid+" .ncla-group-block").forEach(function(b){{'
            f'var n=b.querySelector(".ncla-gname").value.trim()||"All";'
            f'var c=[];b.querySelectorAll(".ncla-cb:checked").forEach(function(x){{c.push(x.dataset.code);}});'
            f'if(c.length)g.push({{group:n,codes:c.sort()}});'
            f'}});'
            f'document.getElementById(wid).value=JSON.stringify(g);'
            f'}}'
            f'window.nclaSerialize=ser;'
            f'window.nclaAddGroup=function(wid){{'
            f'var t=document.querySelector("#ncla-widget-"+wid+" [data-template]").cloneNode(true);'
            f't.removeAttribute("data-template");t.style.display="";'
            f'document.getElementById("ncla-groups-"+wid).appendChild(t);'
            f'}};'
            f'window.nclaRemove=function(btn,wid){{'
            f'var all=document.querySelectorAll("#ncla-groups-"+wid+" .ncla-group-block");'
            f'if(all.length<=1){{btn.closest(".ncla-group-block").querySelectorAll(".ncla-cb").forEach(function(x){{x.checked=false;}});}}'
            f'else{{btn.closest(".ncla-group-block").remove();}}'
            f'ser(wid);'
            f'}};'
            f'}})();</script>'
        )


class LawOfMessiahAdminForm(forms.ModelForm):
    title = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'cols': 120}),
    )
    ncla = forms.CharField(
        required=False,
        widget=NCLAGroupWidget(),
    )

    class Meta:
        model = LawOfMessiah
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._related_choice_maps = {
            'related_lawofmessiah': self._related_commandment_choice_map(),
            'related_steps': self._related_steps_choice_map(),
            'maimonides': self._maimonides_choice_map(),
        }
        self._code_choice_maps = {
            'meir': self._code_choice_map('meir'),
            'chinuch': self._code_choice_map('chinuch'),
        }

        self.fields['related_lawofmessiah'] = forms.MultipleChoiceField(
            choices=list(self._related_choice_maps['related_lawofmessiah'].items()),
            required=False,
            widget=FilteredSelectMultiple('Related Law of Messiah commandments', is_stacked=False),
        )
        self.fields['related_steps'] = forms.MultipleChoiceField(
            choices=list(self._related_choice_maps['related_steps'].items()),
            required=False,
            widget=FilteredSelectMultiple('Related Steps', is_stacked=False),
        )
        self.fields['maimonides'] = forms.MultipleChoiceField(
            choices=list(self._related_choice_maps['maimonides'].items()),
            required=False,
            widget=FilteredSelectMultiple('Maimonides commandments', is_stacked=False),
        )
        self.fields['meir'] = forms.MultipleChoiceField(
            choices=list(self._code_choice_maps['meir'].items()),
            required=False,
            widget=FilteredSelectMultiple('Meir commandments', is_stacked=False),
        )
        self.fields['chinuch'] = forms.MultipleChoiceField(
            choices=list(self._code_choice_maps['chinuch'].items()),
            required=False,
            widget=FilteredSelectMultiple('Chinuch commandments', is_stacked=False),
        )

        if self.instance and self.instance.pk:
            ncla_val = self.instance.ncla or []
            self.fields['ncla'].initial = ncla_val
            related_values = self.instance.related_lawofmessiah or []
            if not related_values:
                related_values = (self.instance.commandments_related_ot or []) + (self.instance.commandments_related_nt or [])
            self.fields['related_lawofmessiah'].initial = self._related_ids(related_values)
            self.fields['related_steps'].initial = [s.id for s in self.instance.related_steps.all()]
            self.fields['maimonides'].initial = self.instance.maimonides or []
            self.fields['meir'].initial = self.instance.meir or []
            self.fields['chinuch'].initial = self.instance.chinuch or []

        valid_codes = ', '.join(code for code, _ in LawOfMessiah.NCLA_CHOICES)
        self.fields['ncla'].help_text = (
            'Check the boxes for each person category and literal application level. '
            'Use "+ Add group" when this commandment has ncla_deviation (different rules per group/context). '
            f'Valid codes: {valid_codes}.'
        )

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 2
                field.widget.attrs['cols'] = 120

        for field_name in ['commentary_rudolph', 'commentary_juster']:
            value = getattr(self.instance, field_name, '') if self.instance else ''
            if value and str(value).strip():
                self.fields[field_name].widget.attrs['rows'] = 12
            else:
                self.fields[field_name].widget.attrs['rows'] = 2

    def _related_commandment_choice_map(self):
        queryset = LawOfMessiah.objects.order_by('id')
        return {item.id: f'{item.id} - {item.title}' for item in queryset}

    def _related_steps_choice_map(self):
        """Map related steps (Commandments) for selection."""
        from walkasjesus_app.models import Commandment
        queryset = Commandment.objects.order_by('id')
        return {str(item.id): f'{item.id} - {item.title}' for item in queryset}

    def _maimonides_choice_map(self):
        """Map Maimonides commandments for selection."""
        from walkasjesus_app.models import Maimonides
        queryset = Maimonides.objects.order_by('id')
        return {item.id: f'{item.id} - {item.commandment}' for item in queryset}

    def _code_choice_map(self, field_name):
        values = set()
        for items in LawOfMessiah.objects.values_list(field_name, flat=True):
            if not items:
                continue
            for code in items:
                if code:
                    values.add(code)
        return {code: code for code in sorted(values)}

    def _related_ids(self, items):
        if not items:
            return []
        related_ids = []
        for item in items:
            if isinstance(item, dict) and item.get('id'):
                related_ids.append(item['id'])
            elif isinstance(item, str):
                related_ids.append(item)
        return related_ids

    def clean_ncla(self):
        import json as _json
        raw = (self.cleaned_data.get('ncla') or '').strip()
        if not raw:
            return []
        try:
            parsed = _json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise forms.ValidationError(f'Invalid JSON: {exc}')
        if not isinstance(parsed, list):
            raise forms.ValidationError('NCLA must be a JSON list of groups.')
        valid_codes = {code for code, _ in LawOfMessiah.NCLA_CHOICES}
        cleaned = []
        for i, entry in enumerate(parsed):
            if not isinstance(entry, dict):
                raise forms.ValidationError(f'Group {i + 1} must be a JSON object with "group" and "codes" keys.')
            group_name = str(entry.get('group', 'All') or 'All').strip()
            codes = entry.get('codes', [])
            if not isinstance(codes, list):
                raise forms.ValidationError(f'Group "{group_name}": "codes" must be a list.')
            bad = [c for c in codes if c not in valid_codes]
            if bad:
                raise forms.ValidationError(f'Group "{group_name}": unknown code(s): {", ".join(bad)}.')
            if codes:
                cleaned.append({'group': group_name, 'codes': sorted(codes)})
        return cleaned

    def clean_related_lawofmessiah(self):
        return self._clean_related_commandments('related_lawofmessiah')

    def clean_related_steps(self):
        """Convert selected step IDs back to Commandment objects."""
        from walkasjesus_app.models import Commandment
        selected_ids = self.cleaned_data.get('related_steps') or []
        return Commandment.objects.filter(id__in=selected_ids)

    def clean_maimonides(self):
        return sorted(set(self.cleaned_data.get('maimonides') or []))

    def clean_meir(self):
        return sorted(set(self.cleaned_data.get('meir') or []))

    def clean_chinuch(self):
        return sorted(set(self.cleaned_data.get('chinuch') or []))

    def _clean_related_commandments(self, field_name):
        """Return just the IDs for storage in JSONField."""
        selected_ids = self.cleaned_data.get(field_name) or []
        return sorted(set(selected_ids)) if selected_ids else []


class LawOfMessiahAdmin(VersionAdmin):
    form = LawOfMessiahAdminForm
    list_display = ['id', 'title', 'is_unique', 'category', 'commandment_type', 'commandment_form', 'source_dataset']
    list_filter = [
        'source_dataset',
        'commandment_type',
        'commandment_form',
        'is_unique',
        'category',
        'ncla_deviation',
        'classical_commandment',
    ]
    search_fields = ['id', 'title', 'commandment', 'category', 'source', 'copyright']
    inlines = [LawOfMessiahBibleReferenceInline, LawOfMessiahDrawingInline]
    fieldsets = (
        ('Core', {
            'fields': (
                'id',
                'title',
                'commandment',
                'commandment_subtitles',
                'category',
                'source_dataset',
                'commandment_type',
                'commandment_form',
                'is_unique',
            ),
        }),
        ('Commentary', {
            'classes': ('collapse',),
            'fields': (
                'commentary_rudolph',
                'commentary_juster',
                'classical_commentators',
            ),
        }),
        ('Classification', {
            'classes': ('collapse',),
            'fields': (
                'ncla',
                'ncla_deviation',
                'classical_commandment',
            ),
        }),
        ('Relations', {
            'classes': ('collapse',),
            'fields': (
                'related_lawofmessiah',
                'related_steps',
                'maimonides',
                'meir',
                'chinuch',
            ),
        }),
        ('Source', {
            'classes': ('collapse',),
            'fields': (
                'source',
                'copyright',
            ),
        }),
    )

    class Media:
        css = {
            'all': ('css/admin/law_of_messiah_admin.css',)
        }


class MediaResourceAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'law_item_display',
        'commandment_item_display',
        'lesson_item_display',
        'media_type',
        'title',
        'author',
        'language',
        'target_audience',
        'song_count',
        'shortmovie_count',
        'testimony_count',
        'sermon_count',
        'movie_count',
        'blog_count',
        'superbook_count',
        'media_total',
    ]
    list_filter = ['media_type', 'language', 'target_audience', 'is_public', 'law_of_messiah', 'commandment', 'lesson']
    search_fields = ['law_of_messiah__id', 'law_of_messiah__title', 'commandment__id', 'commandment__title', 'lesson__id', 'lesson__title', 'title', 'author', 'description', 'img_url', 'url']
    fields = ['law_of_messiah', 'commandment', 'lesson', 'media_type', 'title', 'description', 'img_url', 'url', 'author', 'target_audience', 'language', 'is_public']
    autocomplete_fields = ['law_of_messiah', 'commandment', 'lesson']
    ordering = ['law_of_messiah__id', 'commandment__id', 'lesson__id', 'media_type', 'title']

    def law_item_display(self, obj):
        if not obj.law_of_messiah:
            return '-'
        if obj.law_of_messiah.title:
            return f'{obj.law_of_messiah.id} - {obj.law_of_messiah.title}'
        return obj.law_of_messiah.id

    law_item_display.short_description = 'Law of Messiah item'

    def lesson_item_display(self, obj):
        if not obj.lesson:
            return '-'
        if obj.lesson.title:
            return f'{obj.lesson.id} - {obj.lesson.title}'
        return obj.lesson.id

    lesson_item_display.short_description = 'Lesson item'

    def commandment_item_display(self, obj):
        if not obj.commandment:
            return '-'
        if obj.commandment.title:
            return f'{obj.commandment.id} - {obj.commandment.title}'
        return obj.commandment.id

    commandment_item_display.short_description = 'Commandment item'

    def _scope_queryset(self, obj):
        if obj.law_of_messiah_id:
            return MediaResource.objects.filter(law_of_messiah_id=obj.law_of_messiah_id)
        if obj.commandment_id:
            return MediaResource.objects.filter(commandment_id=obj.commandment_id)
        if obj.lesson_id:
            return MediaResource.objects.filter(lesson_id=obj.lesson_id)
        return MediaResource.objects.none()

    def _scope_type_counts(self, obj):
        if hasattr(obj, '_scope_type_counts_cache'):
            return obj._scope_type_counts_cache
        counts = {
            LawOfMessiahDrawing.MEDIA_TYPE_SONG: 0,
            LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE: 0,
            LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY: 0,
            LawOfMessiahDrawing.MEDIA_TYPE_SERMON: 0,
            LawOfMessiahDrawing.MEDIA_TYPE_MOVIE: 0,
            LawOfMessiahDrawing.MEDIA_TYPE_BLOG: 0,
            LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK: 0,
            LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW: 0,
        }
        for row in self._scope_queryset(obj).values('media_type').annotate(total=Count('id')):
            media_type = row.get('media_type')
            if media_type in counts:
                counts[media_type] = row.get('total', 0)
        obj._scope_type_counts_cache = counts
        return counts

    def media_total(self, obj):
        return self._scope_queryset(obj).count()

    media_total.short_description = 'Total'

    def song_count(self, obj):
        return self._scope_type_counts(obj)[LawOfMessiahDrawing.MEDIA_TYPE_SONG]

    song_count.short_description = 'Songs'

    def shortmovie_count(self, obj):
        return self._scope_type_counts(obj)[LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE]

    shortmovie_count.short_description = 'ShortMovies'

    def testimony_count(self, obj):
        return self._scope_type_counts(obj)[LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY]

    testimony_count.short_description = 'Testimonies'

    def sermon_count(self, obj):
        return self._scope_type_counts(obj)[LawOfMessiahDrawing.MEDIA_TYPE_SERMON]

    sermon_count.short_description = 'Sermons'

    def movie_count(self, obj):
        return self._scope_type_counts(obj)[LawOfMessiahDrawing.MEDIA_TYPE_MOVIE]

    movie_count.short_description = 'Movies'

    def blog_count(self, obj):
        return self._scope_type_counts(obj)[LawOfMessiahDrawing.MEDIA_TYPE_BLOG]

    blog_count.short_description = 'Blogs'

    def superbook_count(self, obj):
        return self._scope_type_counts(obj)[LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK]

    superbook_count.short_description = 'Superbooks'

    def henkieshow_count(self, obj):
        return self._scope_type_counts(obj)[LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW]

    henkieshow_count.short_description = 'Henkieshows'

    def law_media_count(self, obj):
        if not obj.law_of_messiah:
            return 0
        return MediaResource.objects.filter(law_of_messiah=obj.law_of_messiah).count()

    law_media_count.short_description = 'Law media count'

    def step_media_count(self, obj):
        if not obj.commandment:
            return 0
        return MediaResource.objects.filter(commandment=obj.commandment).count()

    step_media_count.short_description = 'Step media count'

    def lesson_media_count(self, obj):
        if not obj.lesson:
            return 0
        return MediaResource.objects.filter(lesson=obj.lesson).count()

    lesson_media_count.short_description = 'Lesson media count'


class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = 'action_time'

    list_filter = [
        'user',
        'content_type',
        'action_flag'
    ]

    search_fields = [
        'object_repr',
        'change_message'
    ]

    list_display = [
        'action_time',
        'user',
        'content_type',
        'long_change_message',
        'action_flag_',
        'change_message',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def action_flag_(self, obj):
        flags = {
            1: "Addition",
            2: "Changed",
            3: "Deleted",
        }
        return flags[obj.action_flag]

    def long_change_message(self, obj):
        if obj.action_flag == DELETION:
            return escape(obj.object_repr)
        else:
            ct = obj.content_type
            return f'[{obj.object_id}] \'{escape(obj.object_repr[:40])}...\', {obj.get_change_message()}'

    long_change_message.allow_tags = True
    long_change_message.admin_order_field = 'object_repr'
    long_change_message.short_description = u'object'


admin.site.register(Bible, BibleAdmin)
admin.site.register(Commandment, CommandmentAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(LawOfMessiah, LawOfMessiahAdmin)
admin.site.register(MediaResource, MediaResourceAdmin)
admin.site.register(File)
admin.site.register(LogEntry, LogEntryAdmin)


class MaimonidesBibleReferenceInline(admin.TabularInline):
    model = MaimonidesBibleReference
    extra = 0
    fields = ('reference_type', 'source_code', 'book', 'begin_chapter', 'begin_verse', 'end_chapter', 'end_verse')
    ordering = ('reference_type', 'source_code', 'book', 'begin_chapter', 'begin_verse', 'id')


class MaimonidesAdminForm(forms.ModelForm):
    meir_codes = forms.CharField(required=False, label='Meir of Rothenburg')
    chinuch_codes = forms.CharField(required=False, label='Sefer HaChinuch')
    rudolph_codes = forms.CharField(required=False, label='Law of Messiah / Rudolph')

    class Meta:
        model = Maimonides
        fields = '__all__'
        widgets = {
            'commandment': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['meir_codes'].widget = forms.TextInput(attrs={'class': 'vTextField'})
        self.fields['chinuch_codes'].widget = forms.TextInput(attrs={'class': 'vTextField'})
        self.fields['rudolph_codes'].widget = forms.TextInput(attrs={'class': 'vTextField'})

        if self.instance and self.instance.pk:
            self.fields['meir_codes'].initial = ', '.join(self.instance.meir or [])
            self.fields['chinuch_codes'].initial = ', '.join(self.instance.chinuch or [])
            self.fields['rudolph_codes'].initial = ', '.join(self.instance.rudolph or [])

    def _parse_code_line(self, value):
        normalized = str(value or '').replace('\n', ',').replace(';', ',')
        return [item.strip() for item in normalized.split(',') if item.strip()]

    def clean_meir_codes(self):
        return self._parse_code_line(self.cleaned_data.get('meir_codes', ''))

    def clean_chinuch_codes(self):
        return self._parse_code_line(self.cleaned_data.get('chinuch_codes', ''))

    def clean_rudolph_codes(self):
        return self._parse_code_line(self.cleaned_data.get('rudolph_codes', ''))

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.meir = self.cleaned_data.get('meir_codes', [])
        instance.chinuch = self.cleaned_data.get('chinuch_codes', [])
        instance.rudolph = self.cleaned_data.get('rudolph_codes', [])
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class MaimonidesAdmin(admin.ModelAdmin):
    form = MaimonidesAdminForm
    list_display = ['id', 'commandment_type', 'commandment_preview', 'meir_summary', 'chinuch_summary', 'cross_reference_count']
    list_filter = ['commandment_type']
    search_fields = ['id', 'commandment', 'meir', 'chinuch', 'rudolph']
    ordering = ['id']
    inlines = [MaimonidesBibleReferenceInline]
    fieldsets = (
        (None, {
            'fields': ('id', 'commandment_type', 'commandment'),
        }),
        ('Cross references', {
            'fields': ('meir_codes', 'chinuch_codes', 'rudolph_codes'),
        }),
    )

    class Media:
        css = {
            'all': ('css/admin/law_of_messiah_admin.css',)
        }

    def commandment_preview(self, obj):
        text = str(obj.commandment or '').strip()
        return text if len(text) <= 100 else f'{text[:97]}...'

    commandment_preview.short_description = 'Commandment'

    def meir_summary(self, obj):
        return ', '.join(obj.meir or [])

    meir_summary.short_description = 'Meir'

    def chinuch_summary(self, obj):
        return ', '.join(obj.chinuch or [])

    chinuch_summary.short_description = 'HaChinuch'

    def cross_reference_count(self, obj):
        return len(obj.meir or []) + len(obj.chinuch or []) + len(obj.rudolph or []) + obj.bible_reference_rows.count()

    cross_reference_count.short_description = 'Cross refs'


admin.site.register(Maimonides, MaimonidesAdmin)
