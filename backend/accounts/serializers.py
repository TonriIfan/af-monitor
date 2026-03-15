from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from rest_framework import serializers

from .demo_data import random_china_login_context, random_cn_name
from .location import build_login_location_payload, location_from_login_context
from .models import PatientProfile

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


class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = [
            'full_name',
            'phone',
            'age',
            'sex',
            'notes',
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    login_context = LoginContextSerializer(required=False)
    profile = PatientProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            'username',
            'password',
            'email',
            'first_name',
            'last_name',
            'login_context',
            'profile',
        ]
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        login_context = validated_data.pop('login_context', None)
        profile_data = validated_data.pop('profile', None) or {}

        user = User(**validated_data)
        user.role = User.Role.USER
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.set_password(password)

        if login_context:
            location = location_from_login_context(login_context)
            user.last_login_ip = (login_context.get('ip') or '').strip()
            user.last_login_country = location['country']
            user.last_login_region = location['region']
            user.last_login_city = location['city']
            user.last_login_latitude = location['latitude']
            user.last_login_longitude = location['longitude']

        user.save()

        full_name = profile_data.get('full_name') or ''.join([part for part in [user.last_name, user.first_name] if part])
        PatientProfile.objects.create(
            user=user,
            full_name=full_name,
            phone=profile_data.get('phone', ''),
            age=profile_data.get('age'),
            sex=profile_data.get('sex', ''),
            notes=profile_data.get('notes', ''),
        )
        return user


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
    generate_china_location = serializers.BooleanField(write_only=True, required=False, default=False)
    login_context = LoginContextSerializer(required=False)

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
            'generate_china_location',
            'login_context',
        ]
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
            'first_name': {'required': False, 'allow_blank': True},
            'last_name': {'required': False, 'allow_blank': True},
            'is_active': {'required': False},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        generate_china_location = validated_data.pop('generate_china_location', False)
        login_context = validated_data.pop('login_context', None)
        user = User(**validated_data)
        user.is_staff = user.role == User.Role.ADMIN
        user.is_superuser = False
        user.set_password(password)
        if generate_china_location:
            login_context = login_context or random_china_login_context()
        if login_context:
            location = location_from_login_context(login_context)
            user.last_login_ip = (login_context.get('ip') or '').strip()
            user.last_login_country = location['country']
            user.last_login_region = location['region']
            user.last_login_city = location['city']
            user.last_login_latitude = location['latitude']
            user.last_login_longitude = location['longitude']
        user.save()
        return user


class UserBatchCreateSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=1, max_value=100)
    username_prefix = serializers.CharField(max_length=32, default='demo-user')
    password = serializers.CharField(min_length=8, default='demo12345')
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.USER)
    is_active = serializers.BooleanField(required=False, default=True)
    generate_china_location = serializers.BooleanField(required=False, default=True)
    generate_profile = serializers.BooleanField(required=False, default=True)
    email_domain = serializers.CharField(max_length=128, required=False, allow_blank=True, default='example.com')

    def create_users(self):
        payload = self.validated_data
        existing_count = User.objects.filter(username__startswith=payload['username_prefix']).count()
        created_users = []

        for index in range(1, payload['count'] + 1):
            sequence = existing_count + index
            username = f"{payload['username_prefix']}{sequence:03d}"
            last_name = ''
            first_name = ''
            if payload['generate_profile']:
                last_name, first_name = random_cn_name()
            email = ''
            if payload['email_domain']:
                email = f"{username}@{payload['email_domain']}"

            serializer = UserCreateSerializer(
                data={
                    'username': username,
                    'password': payload['password'],
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'role': payload['role'],
                    'is_active': payload['is_active'],
                    'generate_china_location': payload['generate_china_location'],
                }
            )
            serializer.is_valid(raise_exception=True)
            created_users.append(serializer.save())

        return created_users


class UserBatchDeleteSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
