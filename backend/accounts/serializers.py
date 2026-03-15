from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from rest_framework import serializers

from .location import build_login_location_payload

User = get_user_model()


class LoginContextSerializer(serializers.Serializer):
    ip = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    region = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)
    country_name = serializers.CharField(required=False, allow_blank=True)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)
    login_context = LoginContextSerializer(required=False)

    def validate(self, attrs):
        request = self.context.get('request')
        user = authenticate(
            request=request,
            username=attrs.get('username'),
            password=attrs.get('password'),
        )
        if not user:
            raise serializers.ValidationError('用户名或密码错误。')
        attrs['user'] = user
        return attrs


class UserSummarySerializer(serializers.ModelSerializer):
    device_count = serializers.IntegerField(read_only=True)
    measurement_count = serializers.IntegerField(read_only=True)
    alert_count = serializers.IntegerField(read_only=True)
    unread_alert_count = serializers.IntegerField(read_only=True)
    latest_activity_at = serializers.DateTimeField(read_only=True)
    last_login_location = serializers.SerializerMethodField()

    def get_last_login_location(self, obj):
        return build_login_location_payload(obj)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login_ip',
            'last_login_location',
            'device_count',
            'measurement_count',
            'alert_count',
            'unread_alert_count',
            'latest_activity_at',
            'date_joined',
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.USER)

    class Meta:
        model = User
        fields = [
            'username',
            'password',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_active',
        ]
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
            'is_active': {'required': False},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.is_staff = user.role == User.Role.ADMIN
        user.is_superuser = False
        user.set_password(password)
        user.save()
        return user
