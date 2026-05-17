"""walkasjesus_website URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from walkasjesus_app.sitemaps import CommandmentSitemap, LessonSitemap, StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'commandments': CommandmentSitemap,
    'lessons': LessonSitemap,
}

urlpatterns = [
    path('', include('walkasjesus_app.urls', namespace='commandments')),
    path('account/', include('account_app.urls', namespace='account')),
    path('rosetta/', include('rosetta.urls')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('admin_portal/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots_txt'),
]

admin.site.site_header = "Walk as Jesus Admin Portal"
admin.site.site_title = "Walk as Jesus"
admin.site.index_title = "Home Administration Portal"

# Not sure why but all tuts only do this in debug mode,
# Is it something special, or just because it is recommended
# to use a different server for file serving?
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
