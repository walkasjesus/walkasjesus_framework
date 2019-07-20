from django.contrib import admin

from .models import *


class BibleReferenceInline(admin.TabularInline):
    model = BibleReference
    extra = 0


class CallingAdmin(admin.ModelAdmin):
    inlines = [
        BibleReferenceInline,
    ]


admin.site.register(Calling, CallingAdmin)
admin.site.register(BibleReference)
