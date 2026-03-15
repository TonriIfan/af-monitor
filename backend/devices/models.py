from django.conf import settings
from django.db import models
from django.db.models import Q


class Device(models.Model):
    device_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128, blank=True)
    device_type = models.CharField(max_length=64, default='smart-ring')
    source = models.CharField(max_length=64, default='wechat-miniapp')
    metadata = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.device_id


class DeviceBinding(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_bindings',
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name='bindings',
    )
    alias = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    bound_at = models.DateTimeField(auto_now_add=True)
    unbound_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-bound_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'device'],
                condition=Q(is_active=True),
                name='unique_active_binding_per_user_device',
            ),
            models.UniqueConstraint(
                fields=['device'],
                condition=Q(is_active=True),
                name='unique_active_binding_per_device',
            ),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.device_id}'

# Create your models here.
