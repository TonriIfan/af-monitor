from django.conf import settings
from django.db import models

from devices.models import Device


class UploadSession(models.Model):
    session_key = models.CharField(max_length=128, unique=True)
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='upload_sessions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='upload_sessions',
    )
    source = models.CharField(max_length=64, default='wechat-miniapp')
    client_started_at = models.DateTimeField(null=True, blank=True)
    last_client_time = models.DateTimeField(null=True, blank=True)
    packet_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.session_key


class RawPacket(models.Model):
    STATUS_PARSED = 'parsed'
    STATUS_UNSUPPORTED = 'unsupported'
    STATUS_INVALID = 'invalid'
    PARSE_STATUS_CHOICES = [
        (STATUS_PARSED, 'parsed'),
        (STATUS_UNSUPPORTED, 'unsupported'),
        (STATUS_INVALID, 'invalid'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='raw_packets')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_packets',
    )
    upload_session = models.ForeignKey(
        UploadSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_packets',
    )
    source = models.CharField(max_length=64, default='wechat-miniapp')
    client_time = models.DateTimeField()
    raw_payload = models.JSONField()
    frame_hex = models.TextField(blank=True)
    frame_bytes = models.JSONField(default=list, blank=True)
    command_code = models.CharField(max_length=8, blank=True)
    subcommand_code = models.CharField(max_length=8, blank=True)
    packet_kind = models.CharField(max_length=64, default='unknown')
    parse_status = models.CharField(
        max_length=16,
        choices=PARSE_STATUS_CHOICES,
        default=STATUS_PARSED,
    )
    parse_error = models.CharField(max_length=255, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']


class Measurement(models.Model):
    raw_packet = models.OneToOneField(
        RawPacket,
        on_delete=models.CASCADE,
        related_name='measurement',
    )
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='measurements')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='measurements',
    )
    measured_at = models.DateTimeField()
    packet_kind = models.CharField(max_length=64, default='unknown')
    parsed = models.JSONField(default=dict, blank=True)
    battery_level = models.PositiveSmallIntegerField(null=True, blank=True)
    battery_state = models.CharField(max_length=32, blank=True)
    heart_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    hrv = models.PositiveSmallIntegerField(null=True, blank=True)
    stress = models.PositiveSmallIntegerField(null=True, blank=True)
    oxygen = models.PositiveSmallIntegerField(null=True, blank=True)
    oxygen_heart_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    oxygen_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    body_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    wear_status = models.CharField(max_length=32, blank=True)
    oxygen_wear_status = models.CharField(max_length=32, blank=True)
    measurement_status = models.CharField(max_length=32, blank=True)
    is_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-measured_at', '-id']


class AnalysisResult(models.Model):
    measurement = models.OneToOneField(
        Measurement,
        on_delete=models.CASCADE,
        related_name='analysis_result',
    )
    raw_packet = models.ForeignKey(
        RawPacket,
        on_delete=models.CASCADE,
        related_name='analysis_results',
    )
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='analysis_results')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analysis_results',
    )
    algorithm_version = models.CharField(max_length=32, default='rules-v1')
    risk_level = models.CharField(max_length=16, default='low')
    risk_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    labels = models.JSONField(default=list, blank=True)
    triggers = models.JSONField(default=list, blank=True)
    details = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)
    should_alert = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AlertEvent(models.Model):
    LEVEL_LOW = 'low'
    LEVEL_MODERATE = 'moderate'
    LEVEL_HIGH = 'high'
    LEVEL_CRITICAL = 'critical'
    LEVEL_CHOICES = [
        (LEVEL_LOW, 'low'),
        (LEVEL_MODERATE, 'moderate'),
        (LEVEL_HIGH, 'high'),
        (LEVEL_CRITICAL, 'critical'),
    ]
    STATUS_UNREAD = 'unread'
    STATUS_READ = 'read'
    STATUS_CHOICES = [
        (STATUS_UNREAD, 'unread'),
        (STATUS_READ, 'read'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alerts')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts',
    )
    measurement = models.ForeignKey(
        Measurement,
        on_delete=models.CASCADE,
        related_name='alerts',
    )
    analysis_result = models.ForeignKey(
        AnalysisResult,
        on_delete=models.CASCADE,
        related_name='alerts',
    )
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES)
    title = models.CharField(max_length=128)
    message = models.TextField()
    trigger_codes = models.JSONField(default=list, blank=True)
    dedupe_key = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_UNREAD,
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AiSettings(models.Model):
    MODE_DISABLED = 'disabled'
    MODE_TEMPLATE = 'template'
    MODE_OPENAI_COMPATIBLE = 'openai_compatible'
    MODE_CHOICES = [
        (MODE_DISABLED, 'disabled'),
        (MODE_TEMPLATE, 'template'),
        (MODE_OPENAI_COMPATIBLE, 'openai_compatible'),
    ]

    singleton_key = models.CharField(max_length=32, unique=True, default='default')
    enabled = models.BooleanField(default=False)
    mode = models.CharField(max_length=32, choices=MODE_CHOICES, default=MODE_TEMPLATE)
    api_base_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    model = models.CharField(max_length=128, default='gpt-4o-mini')
    temperature = models.DecimalField(max_digits=3, decimal_places=2, default=0.20)
    system_prompt = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'AI Settings ({self.mode})'


class SymptomFeedback(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='symptom_feedbacks',
    )
    symptoms = models.JSONField(default=list, blank=True)
    severity = models.PositiveSmallIntegerField(default=1)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at', '-id']


class PushDeviceRegistration(models.Model):
    PLATFORM_IOS = 'ios'
    PLATFORM_ANDROID = 'android'
    PLATFORM_HARMONY = 'harmony'
    PLATFORM_CHOICES = [
        (PLATFORM_IOS, 'ios'),
        (PLATFORM_ANDROID, 'android'),
        (PLATFORM_HARMONY, 'harmony'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_devices',
    )
    device_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    app_version = models.CharField(max_length=32, blank=True)
    device_name = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_seen_at']
