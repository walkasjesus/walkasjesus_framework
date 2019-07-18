from django.contrib import admin

from .models import *


class BibleReferenceInline(admin.TabularInline):
    model = BibleReference


class CallingAdmin(admin.ModelAdmin):
    inlines = [
        BibleReferenceInline,
    ]


admin.site.register(Calling, CallingAdmin)
admin.site.register(BibleReference)
