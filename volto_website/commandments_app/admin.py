from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from .models import *


class PrimaryBibleReferencesInline(admin.TabularInline):
    model = PrimaryBibleReference
    extra = 0


class SecondaryBibleReferenceInline(admin.TabularInline):
    model = SecondaryBibleReference
    extra = 0


class ImageInline(admin.TabularInline):
    model = Image
    extra = 0


class SongInline(admin.TabularInline):
    model = Song
    extra = 0


class SermonInline(admin.TabularInline):
    model = Sermon
    extra = 0


class CommandmentAdmin(TranslationAdmin):
    inlines = [
        PrimaryBibleReferencesInline,
        SecondaryBibleReferenceInline,
        ImageInline,
        SongInline,
        SermonInline,
    ]


admin.site.register(Commandment, CommandmentAdmin)
