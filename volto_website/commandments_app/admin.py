from django.contrib import admin

from .models import *


class PrimaryBibleReferencesInline(admin.TabularInline):
    model = PrimaryBibleReference
    extra = 0


class SecondaryBibleReferenceInline(admin.TabularInline):
    model = SecondaryBibleReference
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


class VideoInline(admin.TabularInline):
    model = Video
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


class BookInline(admin.TabularInline):
    model = Book
    extra = 0


class CommandmentAdmin(admin.ModelAdmin):
    inlines = [
        PrimaryBibleReferencesInline,
        SecondaryBibleReferenceInline,
        QuestionInline,
        DrawingInline,
        SongInline,
        VideoInline,
        SermonInline,
        PictureInline,
        TestimonyInline,
        BookInline,
    ]


admin.site.register(Commandment, CommandmentAdmin)
admin.site.register(File)
