"""jesus_commandments_website URL Configuration

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
from django.urls import include, path

urlpatterns = [
    path('', include('commandments_app.urls', namespace='commandments')),
    path('account/', include('account_app.urls', namespace='account')),
    path('rosetta/', include('rosetta.urls')),
    path('admin_portal/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
]

admin.site.site_header = "Jesus Commandments Admin Portal"
admin.site.site_title = "Jesus Commandments"
admin.site.index_title = "Home Administration Portal"

# Not sure why but all tuts only do this in debug mode,
# Is it something special, or just because it is recommended
# to use a different server for file serving?
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
