from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signup', views.signup, name='signup'),
    path('profile', views.profile, name='profile'),
    path('change_password', views.change_password, name='change_password')
]