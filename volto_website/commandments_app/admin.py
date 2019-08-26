from django.contrib import admin

from .models import *


class PrimaryBibleReferencesInline(admin.TabularInline):
    model = PrimaryBibleReference
    extra = 0


class SecondaryBibleReferenceInline(admin.TabularInline):
    model = SecondaryBibleReference
    extra = 0


class TertiaryBibleReferenceInline(admin.TabularInline):
    model = TertiaryBibleReference
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


class MovieInline(admin.TabularInline):
    model = Movie
    extra = 0


class ShortMovieInline(admin.TabularInline):
    model = ShortMovie
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


class CommandmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'title',  'primary_bible_references', 'category']
    inlines = [
        PrimaryBibleReferencesInline,
        SecondaryBibleReferenceInline,
        TertiaryBibleReferenceInline,
        QuestionInline,
        DrawingInline,
        SongInline,
        MovieInline,
        ShortMovieInline,
        SermonInline,
        PictureInline,
        TestimonyInline,
        BlogInline,
        BookInline,
    ]


admin.site.register(Commandment, CommandmentAdmin)
admin.site.register(File)