from django.utils import timezone
from rest_framework import serializers

from .models import Device, DeviceBinding


class DeviceBindingSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(source='device.device_id', read_only=True)
    device_name = serializers.CharField(source='device.name', read_only=True)

    class Meta:
        model = DeviceBinding
        fields = [
            'id',
            'device_id',
            'device_name',
            'alias',
            'is_active',
            'bound_at',
        ]


class DeviceListSerializer(serializers.ModelSerializer):
    alias = serializers.SerializerMethodField()
    unread_alerts = serializers.IntegerField(read_only=True)
    latest_measurement_at = serializers.DateTimeField(read_only=True)
    owner_user_id = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()

    class Meta:
        model = Device
        fields = [
            'device_id',
            'name',
            'device_type',
            'source',
            'last_seen_at',
            'alias',
            'owner_user_id',
            'owner_username',
            'unread_alerts',
            'latest_measurement_at',
        ]

    def get_alias(self, obj):
        binding = getattr(obj, 'active_binding', None)
        return binding.alias if binding else ''

    def get_owner_user_id(self, obj):
        binding = getattr(obj, 'active_binding', None)
        return binding.user_id if binding else None

    def get_owner_username(self, obj):
        binding = getattr(obj, 'active_binding', None)
        return binding.user.username if binding and binding.user else ''


class DeviceBindSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=64)
    name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    alias = serializers.CharField(max_length=128, required=False, allow_blank=True)
    source = serializers.CharField(max_length=64, required=False, default='wechat-miniapp')
    user_id = serializers.IntegerField(required=False, write_only=True)

    def create(self, validated_data):
        request = self.context['request']
        target_user = self.context.get('scope_user') or request.user
        device, _ = Device.objects.get_or_create(
            device_id=validated_data['device_id'],
            defaults={
                'name': validated_data.get('name', ''),
                'source': validated_data.get('source', 'wechat-miniapp'),
            },
        )

        if validated_data.get('name'):
            device.name = validated_data['name']
        device.source = validated_data.get('source', device.source)
        device.last_seen_at = timezone.now()
        device.save(update_fields=['name', 'source', 'last_seen_at', 'updated_at'])

        DeviceBinding.objects.filter(device=device, is_active=True).exclude(user=target_user).update(
            is_active=False,
            unbound_at=timezone.now(),
        )

        binding, created = DeviceBinding.objects.get_or_create(
            user=target_user,
            device=device,
            is_active=True,
            defaults={'alias': validated_data.get('alias', '')},
        )
        if not created:
            binding.alias = validated_data.get('alias', binding.alias)
            binding.save(update_fields=['alias'])
        return binding
