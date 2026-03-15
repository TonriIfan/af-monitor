from rest_framework import serializers

from .models import AiSettings, AlertEvent, Measurement


class PacketIngestSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=64)
    client_time = serializers.DateTimeField()
    source = serializers.CharField(max_length=64, default='wechat-miniapp')
    session_key = serializers.CharField(max_length=128, required=False, allow_blank=True)
    payload = serializers.JSONField()

    def validate_payload(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('payload 必须是对象。')
        if 'frame_hex' not in value and 'frame_bytes' not in value:
            raise serializers.ValidationError('payload 至少需要 frame_hex 或 frame_bytes。')
        return value


class MeasurementSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(source='device.device_id', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='')
    raw_payload = serializers.JSONField(source='raw_packet.raw_payload', read_only=True)
    analysis = serializers.SerializerMethodField()
    alert_state = serializers.SerializerMethodField()

    class Meta:
        model = Measurement
        fields = [
            'id',
            'device_id',
            'user_id',
            'username',
            'measured_at',
            'packet_kind',
            'raw_payload',
            'parsed',
            'analysis',
            'alert_state',
        ]

    def get_analysis(self, obj):
        result = getattr(obj, 'analysis_result', None)
        if not result:
            return None
        return {
            'algorithm_version': result.algorithm_version,
            'risk_level': result.risk_level,
            'risk_score': float(result.risk_score),
            'labels': result.labels,
            'triggers': result.triggers,
            'details': result.details,
            'summary': result.summary,
            'should_alert': result.should_alert,
        }

    def get_alert_state(self, obj):
        alert = obj.alerts.order_by('-created_at').first()
        if not alert:
            return {
                'has_alert': False,
                'latest_alert_id': None,
                'level': None,
                'status': None,
            }
        return {
            'has_alert': True,
            'latest_alert_id': alert.id,
            'level': alert.level,
            'status': alert.status,
        }


class AlertSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(source='device.device_id', read_only=True)
    measurement_id = serializers.IntegerField(source='measurement.id', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = AlertEvent
        fields = [
            'id',
            'device_id',
            'user_id',
            'username',
            'measurement_id',
            'level',
            'title',
            'message',
            'trigger_codes',
            'status',
            'is_read',
            'read_at',
            'created_at',
        ]


class AlertStateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertEvent
        fields = []

    def update(self, instance, validated_data):
        from django.utils import timezone

        instance.status = AlertEvent.STATUS_READ
        instance.is_read = True
        instance.read_at = timezone.now()
        instance.save(update_fields=['status', 'is_read', 'read_at'])
        return instance


class DeviceStatusSerializer(serializers.Serializer):
    device_id = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    source = serializers.CharField()
    last_seen_at = serializers.DateTimeField(allow_null=True)
    unread_alerts = serializers.IntegerField()
    latest_measurement = serializers.DictField(allow_null=True)


class DashboardOverviewSerializer(serializers.Serializer):
    counts = serializers.DictField()
    user_summaries = serializers.ListField()
    risk_distribution = serializers.ListField()
    latest_measurements = serializers.ListField()
    latest_alerts = serializers.ListField()


class MeasurementTrendSerializer(serializers.Serializer):
    daily = serializers.ListField()
    weekly = serializers.ListField()


class AiSettingsSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_api_key = serializers.SerializerMethodField()
    api_key_masked = serializers.SerializerMethodField()

    class Meta:
        model = AiSettings
        fields = [
            'enabled',
            'mode',
            'api_base_url',
            'api_key',
            'api_key_masked',
            'has_api_key',
            'model',
            'temperature',
            'system_prompt',
            'updated_at',
        ]
        read_only_fields = ['updated_at', 'api_key_masked', 'has_api_key']

    def get_has_api_key(self, obj):
        return bool(obj.api_key)

    def get_api_key_masked(self, obj):
        if not obj.api_key:
            return ''
        if len(obj.api_key) <= 8:
            return '*' * len(obj.api_key)
        return f'{obj.api_key[:4]}{"*" * (len(obj.api_key) - 8)}{obj.api_key[-4:]}'

    def update(self, instance, validated_data):
        api_key = validated_data.pop('api_key', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if api_key is not None:
            instance.api_key = api_key
        instance.save()
        return instance
