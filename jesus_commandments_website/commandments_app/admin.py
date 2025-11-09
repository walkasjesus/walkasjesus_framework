from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.models import LogEntry, DELETION
from django.urls import path, reverse
from django.utils.html import escape
from reversion.admin import VersionAdmin
from django.db.models import Count, Q

from commandments_app.models import *
from commandments_app.models.commandment_question import Question
from commandments_app.models.lesson_question import LessonQuestion
from commandments_app.models.lesson_media import *
from commandments_app.views.admin.admin_bible_view import AdminBibleView


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
admin.site.register(File)
admin.site.register(LogEntry, LogEntryAdmin)
