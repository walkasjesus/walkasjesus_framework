from django.contrib import admin

from .models import *


class PrimaryBibleReferenceInline(admin.TabularInline):
    model = PrimaryBibleReference


class SecondaryBibleReferenceInline(admin.TabularInline):
    model = SecondaryBibleReference
    extra = 0


class ImageInline(admin.TabularInline):
    model = Image
    extra = 0


class CallingAdmin(admin.ModelAdmin):
    inlines = [
        PrimaryBibleReferenceInline,
        SecondaryBibleReferenceInline,
        ImageInline
    ]


admin.site.register(Calling, CallingAdmin)
