from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import ListCreateAPIView
from rest_framework.views import APIView
from rest_framework.generics import DestroyAPIView
from rest_framework.response import Response

from .location import apply_login_location, build_login_location_payload
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserBatchCreateSerializer,
    UserBatchDeleteSerializer,
    UserCreateSerializer,
    UserSummarySerializer,
)

User = get_user_model()


def resolve_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def build_auth_payload(user, token_key: str) -> dict:
    return {
        'token': token_key,
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
    }


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
        return Response(build_auth_payload(user, token.key), status=status.HTTP_200_OK)


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
        return Response(build_auth_payload(user, token.key), status=status.HTTP_200_OK)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(build_auth_payload(user, token.key), status=status.HTTP_201_CREATED)


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


class UserBatchCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = UserBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = serializer.create_users()
        queryset = (
            User.objects.filter(pk__in=[user.pk for user in users])
            .annotate(
                device_count=Count('device_bindings__device', filter=Q(device_bindings__is_active=True), distinct=True),
                measurement_count=Count('measurements', distinct=True),
                alert_count=Count('alerts', distinct=True),
                unread_alert_count=Count('alerts', filter=Q(alerts__status='unread'), distinct=True),
                latest_activity_at=Max('measurements__measured_at'),
            )
            .order_by('username')
        )
        return Response(UserSummarySerializer(queryset, many=True).data, status=status.HTTP_201_CREATED)


class UserDetailView(DestroyAPIView):
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all()

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response({'detail': '不能删除当前登录账号。'}, status=status.HTTP_400_BAD_REQUEST)
        username = user.username
        self.perform_destroy(user)
        return Response({'deleted': True, 'username': username}, status=status.HTTP_200_OK)


class UserBatchDeleteView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = UserBatchDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = set(serializer.validated_data['user_ids'])
        if request.user.pk in user_ids:
            return Response({'detail': '批量删除中不能包含当前登录账号。'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = User.objects.filter(pk__in=user_ids)
        usernames = list(queryset.values_list('username', flat=True))
        deleted_count = queryset.count()
        queryset.delete()
        return Response(
            {
                'deleted': True,
                'deleted_count': deleted_count,
                'usernames': usernames,
            },
            status=status.HTTP_200_OK,
        )
