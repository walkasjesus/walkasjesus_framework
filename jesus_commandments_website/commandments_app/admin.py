from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from django.urls import path, reverse
from django.utils.html import escape
from reversion.admin import VersionAdmin

from commandments_app.models import *
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
    list_display = ['id', 'title', 'primary_bible_reference', 'category']
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
admin.site.register(File)
admin.site.register(LogEntry, LogEntryAdmin)
