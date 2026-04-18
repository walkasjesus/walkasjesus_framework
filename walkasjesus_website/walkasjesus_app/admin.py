from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.admin.widgets import FilteredSelectMultiple
from django import forms
from django.urls import path, reverse
from django.utils.html import escape
from reversion.admin import VersionAdmin
from django.db.models import Count, Q

from walkasjesus_app.models import *
from walkasjesus_app.models.commandment_question import Question
from walkasjesus_app.models.lesson_question import LessonQuestion
from walkasjesus_app.models.lesson_media import *
from walkasjesus_app.views.admin.admin_bible_view import AdminBibleView


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


class CommandmentAdmin(VersionAdmin):
    class Meta:
        verbose_name_plural = 'Step'

    list_display = [
        'id',
        'title',
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
    list_filter = [MediaTargetAudienceFilter, MediaLanguageFilter]
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
        DrawingInline,
        SongInline,
        SuperbookInline,
        HenkieshowInline,
        MovieInline,
        ShortMovieInline,
        WaJVideoInline,
        SermonInline,
        PictureInline,
        TestimonyInline,
        BlogInline,
        BookInline,
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
    inlines = [
        LessonQuestionInline,
        LessonSongInline,
        LessonSuperbookInline,
        LessonHenkieshowInline,
        LessonShortMovieInline,
        LessonPictureInline,
        LessonTestimonyInline,
        LessonDrawingInline,
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
    fields = ['author', 'description', 'img_url', 'is_public']


class LawOfMessiahAdminForm(forms.ModelForm):
    title = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'cols': 120}),
    )
    ncla = forms.MultipleChoiceField(
        choices=LawOfMessiah.NCLA_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = LawOfMessiah
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._related_choice_maps = {
            'commandments_related_ot': self._related_commandment_choice_map(LawOfMessiah.SOURCE_DATASET_OT),
            'commandments_related_nt': self._related_commandment_choice_map(LawOfMessiah.SOURCE_DATASET_NT),
        }
        self._code_choice_maps = {
            'maimonides': self._code_choice_map('maimonides'),
            'meir': self._code_choice_map('meir'),
            'chinuch': self._code_choice_map('chinuch'),
        }

        self.fields['commandments_related_ot'] = forms.MultipleChoiceField(
            choices=list(self._related_choice_maps['commandments_related_ot'].items()),
            required=False,
            widget=FilteredSelectMultiple('Related OT commandments', is_stacked=False),
        )
        self.fields['commandments_related_nt'] = forms.MultipleChoiceField(
            choices=list(self._related_choice_maps['commandments_related_nt'].items()),
            required=False,
            widget=FilteredSelectMultiple('Related NT commandments', is_stacked=False),
        )
        self.fields['maimonides'] = forms.MultipleChoiceField(
            choices=list(self._code_choice_maps['maimonides'].items()),
            required=False,
            widget=FilteredSelectMultiple('Maimonides', is_stacked=False),
        )
        self.fields['meir'] = forms.MultipleChoiceField(
            choices=list(self._code_choice_maps['meir'].items()),
            required=False,
            widget=FilteredSelectMultiple('Meir', is_stacked=False),
        )
        self.fields['chinuch'] = forms.MultipleChoiceField(
            choices=list(self._code_choice_maps['chinuch'].items()),
            required=False,
            widget=FilteredSelectMultiple('Chinuch', is_stacked=False),
        )

        if self.instance and self.instance.pk:
            self.fields['ncla'].initial = self.instance.ncla or []
            self.fields['commandments_related_ot'].initial = self._related_ids(self.instance.commandments_related_ot)
            self.fields['commandments_related_nt'].initial = self._related_ids(self.instance.commandments_related_nt)
            self.fields['maimonides'].initial = self.instance.maimonides or []
            self.fields['meir'].initial = self.instance.meir or []
            self.fields['chinuch'].initial = self.instance.chinuch or []

        self.fields['ncla'].help_text = (
            'NCLA = Person category + literal application code. '
            'Example: JMm means Jewish male, literal compliance mandated.'
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

    def _related_commandment_choice_map(self, source_dataset):
        queryset = LawOfMessiah.objects.filter(source_dataset=source_dataset).order_by('id')
        return {item.id: f'{item.id} - {item.title}' for item in queryset}

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
        values = self.cleaned_data.get('ncla') or []
        return sorted(set(values))

    def clean_commandments_related_ot(self):
        return self._clean_related_commandments('commandments_related_ot')

    def clean_commandments_related_nt(self):
        return self._clean_related_commandments('commandments_related_nt')

    def clean_maimonides(self):
        return sorted(set(self.cleaned_data.get('maimonides') or []))

    def clean_meir(self):
        return sorted(set(self.cleaned_data.get('meir') or []))

    def clean_chinuch(self):
        return sorted(set(self.cleaned_data.get('chinuch') or []))

    def _clean_related_commandments(self, field_name):
        selected_ids = self.cleaned_data.get(field_name) or []
        choice_map = self._related_choice_maps[field_name]
        cleaned = []
        for item_id in selected_ids:
            label = choice_map.get(item_id, item_id)
            title = label.split(' - ', 1)[1] if ' - ' in label else ''
            cleaned.append({'id': item_id, 'title': title})
        return cleaned


class LawOfMessiahAdmin(VersionAdmin):
    form = LawOfMessiahAdminForm
    list_display = ['id', 'title', 'category', 'commandment_type', 'commandment_form', 'source_dataset']
    list_filter = ['source_dataset', 'commandment_type', 'commandment_form', 'category', 'ncla_deviation', 'classical_commandment']
    search_fields = ['id', 'title', 'commandment', 'category']
    inlines = [LawOfMessiahBibleReferenceInline, LawOfMessiahDrawingInline]
    fieldsets = (
        ('Core', {
            'fields': (
                'id',
                'title',
                'commandment',
                'category',
                'source_dataset',
                'commandment_type',
                'commandment_form',
            ),
        }),
        ('Commentary', {
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
                'commandments_related_ot',
                'commandments_related_nt',
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
admin.site.register(File)
admin.site.register(LogEntry, LogEntryAdmin)
