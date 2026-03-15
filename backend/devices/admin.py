from django.contrib import admin

from .models import Device, DeviceBinding

admin.site.register(Device)
admin.site.register(DeviceBinding)

# Register your models here.
