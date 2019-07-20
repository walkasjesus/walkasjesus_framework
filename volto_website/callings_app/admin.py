from django.contrib import admin

from .models import *


class BibleReferenceInline(admin.TabularInline):
    model = BibleReference
    extra = 0


class ImageInline(admin.TabularInline):
    model = Image
    extra = 0


class CallingAdmin(admin.ModelAdmin):
    inlines = [
        BibleReferenceInline,
        ImageInline
    ]


admin.site.register(Calling, CallingAdmin)
