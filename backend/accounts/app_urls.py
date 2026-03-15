from django.urls import path

from .views import LogoutView, MeView, ProfileView

urlpatterns = [
    path('auth/me', MeView.as_view(), name='auth-me'),
    path('auth/logout', LogoutView.as_view(), name='auth-logout'),
    path('profile', ProfileView.as_view(), name='profile'),
]
