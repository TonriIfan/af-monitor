from django.urls import path

from .views import ConsoleLoginView, LoginView, UserBatchCreateView, UserBatchDeleteView, UserDetailView, UserManagementView

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('console-login', ConsoleLoginView.as_view(), name='auth-console-login'),
    path('users', UserManagementView.as_view(), name='auth-users'),
    path('users/batch', UserBatchCreateView.as_view(), name='auth-users-batch'),
    path('users/batch-delete', UserBatchDeleteView.as_view(), name='auth-users-batch-delete'),
    path('users/<int:pk>', UserDetailView.as_view(), name='auth-user-detail'),
]
