from django.urls import path

from .views import ConsoleLoginView, LoginView, UserManagementView

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('console-login', ConsoleLoginView.as_view(), name='auth-console-login'),
    path('users', UserManagementView.as_view(), name='auth-users'),
]
