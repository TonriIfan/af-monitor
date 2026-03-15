from django.urls import path

from .views import (
    AlertListView,
    AlertReadView,
    AiSettingsView,
    AiSettingsTestView,
    DashboardOverviewView,
    MeasurementLatestView,
    MeasurementLlmInsightView,
    MeasurementListView,
    MeasurementTrendView,
    PacketIngestView,
)

urlpatterns = [
    path('dashboard/overview', DashboardOverviewView.as_view(), name='dashboard-overview'),
    path('packets', PacketIngestView.as_view(), name='packet-ingest'),
    path('measurements', MeasurementListView.as_view(), name='measurement-list'),
    path('measurements/latest', MeasurementLatestView.as_view(), name='measurement-latest'),
    path('measurements/trends', MeasurementTrendView.as_view(), name='measurement-trends'),
    path('measurements/<int:measurement_id>/llm-insight', MeasurementLlmInsightView.as_view(), name='measurement-llm-insight'),
    path('ai/settings', AiSettingsView.as_view(), name='ai-settings'),
    path('ai/settings/test', AiSettingsTestView.as_view(), name='ai-settings-test'),
    path('alerts', AlertListView.as_view(), name='alert-list'),
    path('alerts/<int:alert_id>/read', AlertReadView.as_view(), name='alert-read'),
]
