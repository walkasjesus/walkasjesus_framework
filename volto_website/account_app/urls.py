from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = 'account_app'
urlpatterns = [
    path('', views.index, name='index'),
    path('login', LoginView.as_view(), name='login'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('signup', views.signup, name='signup'),
    path('profile', views.profile, name='profile'),
    path('change_password', views.change_password, name='change_password')
]
