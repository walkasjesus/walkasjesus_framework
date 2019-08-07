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


class ImageInline(admin.TabularInline):
    model = Image
    extra = 0


class ImageUrlInline(admin.TabularInline):
    model = ImageUrl
    extra = 0


class SongInline(admin.TabularInline):
    model = Song
    extra = 0


class SongUrlInline(admin.TabularInline):
    model = SongUrl
    extra = 0


class VideoInline(admin.TabularInline):
    model = Video
    extra = 0


class VideoUrlInline(admin.TabularInline):
    model = VideoUrl
    extra = 0


class SermonInline(admin.TabularInline):
    model = Sermon
    extra = 0


class SermonUrlInline(admin.TabularInline):
    model = SermonUrl
    extra = 0


class CommandmentAdmin(admin.ModelAdmin):
    inlines = [
        PrimaryBibleReferencesInline,
        SecondaryBibleReferenceInline,
        QuestionInline,
        ImageUrlInline,
        SongUrlInline,
        VideoUrlInline,
        SermonUrlInline,
        ImageInline,
        SongInline,
        VideoInline,
        SermonInline,
    ]


admin.site.register(Commandment, CommandmentAdmin)
