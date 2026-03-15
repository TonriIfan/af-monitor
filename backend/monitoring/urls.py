from django.urls import path

from .views import (
    AlertListView,
    AlertReadView,
    DashboardOverviewView,
    MeasurementLatestView,
    MeasurementListView,
    PacketIngestView,
)

urlpatterns = [
    path('dashboard/overview', DashboardOverviewView.as_view(), name='dashboard-overview'),
    path('packets', PacketIngestView.as_view(), name='packet-ingest'),
    path('measurements', MeasurementListView.as_view(), name='measurement-list'),
    path('measurements/latest', MeasurementLatestView.as_view(), name='measurement-latest'),
    path('alerts', AlertListView.as_view(), name='alert-list'),
    path('alerts/<int:alert_id>/read', AlertReadView.as_view(), name='alert-read'),
]
