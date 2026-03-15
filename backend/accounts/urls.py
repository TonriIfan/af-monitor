from django.urls import path

from .views import LoginView, UserManagementView

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('users', UserManagementView.as_view(), name='auth-users'),
]
