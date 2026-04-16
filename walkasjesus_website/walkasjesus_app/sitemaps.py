from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from walkasjesus_app.models import Commandment, Lesson


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return [
            'commandments:index',
            'commandments:listing',
            'commandments:lesson_listing',
            'commandments:vision',
            'commandments:legalism',
        ]

    def location(self, item):
        return reverse(item)


class CommandmentSitemap(Sitemap):
    priority = 0.9
    changefreq = 'monthly'

    def items(self):
        return Commandment.objects.all()

    def location(self, item):
        return reverse('commandments:detail', args=[item.pk])


class LessonSitemap(Sitemap):
    priority = 0.7
    changefreq = 'monthly'

    def items(self):
        return Lesson.objects.all()

    def location(self, item):
        return reverse('commandments:lessondetail', args=[item.pk])
