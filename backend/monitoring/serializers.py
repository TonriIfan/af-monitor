from rest_framework import serializers

from .models import (
    AiSettings,
    AlertEvent,
    AlertPushDelivery,
    Measurement,
    PpgAnalysisRecord,
    PushDeviceRegistration,
    SymptomFeedback,
)
from .services import trigger_labels


class PacketIngestSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=64)
    user_id = serializers.IntegerField(required=False, write_only=True)
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
            'triggers': trigger_labels(result.triggers),
            'trigger_codes': result.triggers,
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
    trigger_labels = serializers.SerializerMethodField()
    push_delivery_summary = serializers.SerializerMethodField()

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
            'trigger_labels',
            'push_delivery_summary',
            'status',
            'is_read',
            'read_at',
            'created_at',
        ]

    def get_trigger_labels(self, obj):
        return trigger_labels(obj.trigger_codes)

    def get_push_delivery_summary(self, obj):
        deliveries = list(obj.push_deliveries.all())
        counts = {
            AlertPushDelivery.STATUS_PENDING: 0,
            AlertPushDelivery.STATUS_SENT: 0,
            AlertPushDelivery.STATUS_FAILED: 0,
            AlertPushDelivery.STATUS_SKIPPED: 0,
        }
        latest_error = ''
        for delivery in deliveries:
            counts[delivery.status] = counts.get(delivery.status, 0) + 1
            if delivery.last_error:
                latest_error = delivery.last_error

        total = len(deliveries)
        status_key = 'not_queued'
        status_label = '未入队'
        if total:
            if counts[AlertPushDelivery.STATUS_SENT] == total:
                status_key = AlertPushDelivery.STATUS_SENT
                status_label = '已发送'
            elif counts[AlertPushDelivery.STATUS_PENDING]:
                status_key = AlertPushDelivery.STATUS_PENDING
                status_label = '待发送'
            elif counts[AlertPushDelivery.STATUS_FAILED]:
                status_key = AlertPushDelivery.STATUS_FAILED
                status_label = '发送失败'
            elif counts[AlertPushDelivery.STATUS_SKIPPED] == total:
                status_key = AlertPushDelivery.STATUS_SKIPPED
                status_label = '已跳过'
            else:
                status_key = 'mixed'
                status_label = '部分完成'

        return {
            'status': status_key,
            'status_label': status_label,
            'total': total,
            'pending_count': counts[AlertPushDelivery.STATUS_PENDING],
            'sent_count': counts[AlertPushDelivery.STATUS_SENT],
            'failed_count': counts[AlertPushDelivery.STATUS_FAILED],
            'skipped_count': counts[AlertPushDelivery.STATUS_SKIPPED],
            'latest_error': latest_error,
        }


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


class MeasurementBatchIngestSerializer(serializers.Serializer):
    items = serializers.ListField(child=PacketIngestSerializer(), allow_empty=False)


class SymptomFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = SymptomFeedback
        fields = [
            'id',
            'symptoms',
            'severity',
            'duration_minutes',
            'notes',
            'occurred_at',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PushDeviceRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushDeviceRegistration
        fields = [
            'id',
            'provider',
            'device_token',
            'platform',
            'app_version',
            'device_name',
            'is_active',
            'last_seen_at',
            'created_at',
        ]
        read_only_fields = ['id', 'last_seen_at', 'created_at']


class PpgAnalyzeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    device_id = serializers.CharField(max_length=64)
    collected_at = serializers.DateTimeField()
    source = serializers.CharField(max_length=64, default='app_upload')
    sample_rate_hz = serializers.FloatField(min_value=10, max_value=500)
    samples = serializers.ListField(
        child=serializers.FloatField(),
        min_length=100,
        allow_empty=False,
    )

    def validate(self, attrs):
        sample_rate_hz = attrs['sample_rate_hz']
        window_seconds = len(attrs['samples']) / sample_rate_hz if sample_rate_hz else 0
        if window_seconds < 5:
            raise serializers.ValidationError('PPG 窗口时长至少需要 5 秒。')
        if window_seconds > 60:
            raise serializers.ValidationError('PPG 窗口时长不能超过 60 秒。')
        attrs['window_seconds'] = round(window_seconds, 2)
        return attrs


class PpgAnalysisRecordSerializer(serializers.ModelSerializer):
    device_id = serializers.CharField(source='device.device_id', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = PpgAnalysisRecord
        fields = [
            'id',
            'user_id',
            'device_id',
            'collected_at',
            'source',
            'sample_rate_hz',
            'window_seconds',
            'sample_count',
            'quality_pass',
            'quality_score',
            'af_probability',
            'af_label',
            'model_version',
            'model_source',
            'features',
            'created_at',
        ]
