from django.urls import path

from .views import DeviceBindView, DeviceListView, DeviceStatusView

urlpatterns = [
    path('', DeviceListView.as_view(), name='device-list'),
    path('bind', DeviceBindView.as_view(), name='device-bind'),
    path('<str:device_id>/status', DeviceStatusView.as_view(), name='device-status'),
]
