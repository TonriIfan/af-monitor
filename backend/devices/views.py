from django.db.models import Count, Max, Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from monitoring.serializers import DeviceStatusSerializer
from monitoring.services import devices_queryset_for_scope, get_device_status_payload, scope_user_for_request

from .models import Device, DeviceBinding
from .serializers import DeviceBindSerializer, DeviceBindingSerializer, DeviceListSerializer


class DeviceListView(generics.ListAPIView):
    serializer_class = DeviceListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        scope_user = scope_user_for_request(self.request)
        return (
            devices_queryset_for_scope(scope_user)
            .prefetch_related(
                Prefetch(
                    'bindings',
                    queryset=DeviceBinding.objects.select_related('user').filter(
                        is_active=True,
                        user=scope_user,
                    )
                    if scope_user is not None
                    else DeviceBinding.objects.select_related('user').filter(is_active=True),
                    to_attr='active_binding_list',
                )
            )
            .annotate(
                unread_alerts=Count('alerts', filter=Q(alerts__status='unread')),
                latest_measurement_at=Max('measurements__measured_at'),
            )
            .distinct()
        )

    def list(self, request, *args, **kwargs):
        queryset = list(self.get_queryset())
        for device in queryset:
            device.active_binding = device.active_binding_list[0] if device.active_binding_list else None
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class DeviceBindView(generics.CreateAPIView):
    serializer_class = DeviceBindSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'scope_user': scope_user_for_request(request)},
        )
        serializer.is_valid(raise_exception=True)
        binding = serializer.save()
        return Response(
            DeviceBindingSerializer(binding).data,
            status=status.HTTP_201_CREATED,
        )


class DeviceStatusView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DeviceStatusSerializer
    lookup_url_kwarg = 'device_id'

    def get_object(self):
        scope_user = scope_user_for_request(self.request)
        device = get_object_or_404(
            devices_queryset_for_scope(scope_user),
            device_id=self.kwargs[self.lookup_url_kwarg],
        )
        return get_device_status_payload(device, scope_user)
