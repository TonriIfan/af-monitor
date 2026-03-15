from django.contrib import admin

from .models import AlertEvent, AnalysisResult, Measurement, RawPacket, UploadSession

admin.site.register(UploadSession)
admin.site.register(RawPacket)
admin.site.register(Measurement)
admin.site.register(AnalysisResult)
admin.site.register(AlertEvent)

# Register your models here.
