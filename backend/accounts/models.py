from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        USER = 'user', 'User'

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.USER)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_country = models.CharField(max_length=64, blank=True)
    last_login_region = models.CharField(max_length=128, blank=True)
    last_login_city = models.CharField(max_length=128, blank=True)
    last_login_latitude = models.FloatField(null=True, blank=True)
    last_login_longitude = models.FloatField(null=True, blank=True)

    @property
    def is_console_admin(self) -> bool:
        return self.role == self.Role.ADMIN and self.is_staff


class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    full_name = models.CharField(max_length=128, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=16, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.full_name or self.user.username
