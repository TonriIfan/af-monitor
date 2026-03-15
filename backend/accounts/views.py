from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response

from .location import apply_login_location, build_login_location_payload
from .serializers import LoginSerializer, UserCreateSerializer, UserSummarySerializer

User = get_user_model()


def resolve_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class LoginView(ObtainAuthToken):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        apply_login_location(
            user,
            resolve_client_ip(request),
            serializer.validated_data.get('login_context'),
        )
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                    'last_login_ip': user.last_login_ip,
                    'last_login_location': build_login_location_payload(user),
                },
            },
            status=status.HTTP_200_OK,
        )


class ConsoleLoginView(LoginView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        if not user.is_console_admin:
            return Response(
                {'detail': '只有管理员账号可以登录控制台。'},
                status=status.HTTP_403_FORBIDDEN,
            )
        apply_login_location(
            user,
            resolve_client_ip(request),
            serializer.validated_data.get('login_context'),
        )
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                    'last_login_ip': user.last_login_ip,
                    'last_login_location': build_login_location_payload(user),
                },
            },
            status=status.HTTP_200_OK,
        )


class UserManagementView(ListCreateAPIView):
    permission_classes = [permissions.IsAdminUser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserSummarySerializer

    def get_queryset(self):
        return (
            User.objects.all()
            .annotate(
                device_count=Count('device_bindings__device', filter=Q(device_bindings__is_active=True), distinct=True),
                measurement_count=Count('measurements', distinct=True),
                alert_count=Count('alerts', distinct=True),
                unread_alert_count=Count('alerts', filter=Q(alerts__status='unread'), distinct=True),
                latest_activity_at=Max('measurements__measured_at'),
            )
            .order_by('-is_staff', 'username')
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        summary = UserSummarySerializer(
            self.get_queryset().get(pk=user.pk),
            context={'request': request},
        )
        return Response(summary.data, status=status.HTTP_201_CREATED)
