from django.urls import path

from .views import DeviceBindView, DeviceCurrentView, DeviceListView, DeviceStatusView, DeviceUnbindView

urlpatterns = [
    path('', DeviceListView.as_view(), name='device-list'),
    path('bind', DeviceBindView.as_view(), name='device-bind'),
    path('current', DeviceCurrentView.as_view(), name='device-current'),
    path('unbind', DeviceUnbindView.as_view(), name='device-unbind'),
    path('<str:device_id>/status', DeviceStatusView.as_view(), name='device-status'),
]
