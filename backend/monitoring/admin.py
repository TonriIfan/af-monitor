from django.contrib import admin

from .models import (
    AlertEvent,
    AlertPushDelivery,
    AnalysisResult,
    Measurement,
    PushDeviceRegistration,
    RawPacket,
    UploadSession,
)

admin.site.register(UploadSession)
admin.site.register(RawPacket)
admin.site.register(Measurement)
admin.site.register(AnalysisResult)
admin.site.register(AlertEvent)
admin.site.register(PushDeviceRegistration)
admin.site.register(AlertPushDelivery)

# Register your models here.
