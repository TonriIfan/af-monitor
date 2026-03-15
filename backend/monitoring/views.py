import json

from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .llm import build_measurement_llm_context, request_llm_insight
from .llm import get_ai_settings
from .models import AiSettings, AlertEvent, Measurement
from .serializers import (
    AlertSerializer,
    AlertStateUpdateSerializer,
    AiSettingsSerializer,
    DashboardOverviewSerializer,
    MeasurementTrendSerializer,
    MeasurementSerializer,
    PacketIngestSerializer,
)
from .services import (
    alerts_queryset_for_scope,
    build_dashboard_overview,
    build_measurement_trends,
    ingest_packet,
    measurements_queryset_for_scope,
    scope_user_for_request,
)


class PacketIngestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PacketIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_request_payload = json.loads(json.dumps(request.data))
        bundle = ingest_packet(
            validated_data=serializer.validated_data,
            raw_payload=raw_request_payload,
            request_user=request.user if request.user.is_authenticated else None,
        )
        return Response(
            MeasurementSerializer(bundle['measurement']).data,
            status=status.HTTP_201_CREATED,
        )


class MeasurementListView(generics.ListAPIView):
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        scope_user = scope_user_for_request(self.request)
        queryset = measurements_queryset_for_scope(scope_user).select_related('raw_packet')

        device_id = self.request.query_params.get('device_id')
        start = self.request.query_params.get('start')
        end = self.request.query_params.get('end')

        if device_id:
            queryset = queryset.filter(device__device_id=device_id)
        if start:
            parsed = parse_datetime(start)
            if parsed:
                queryset = queryset.filter(measured_at__gte=parsed)
        if end:
            parsed = parse_datetime(end)
            if parsed:
                queryset = queryset.filter(measured_at__lte=parsed)
        return queryset


class MeasurementLatestView(generics.RetrieveAPIView):
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        scope_user = scope_user_for_request(self.request)
        queryset = measurements_queryset_for_scope(scope_user).select_related('raw_packet')
        device_id = self.request.query_params.get('device_id')
        if device_id:
            queryset = queryset.filter(device__device_id=device_id)
        return queryset.first()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance:
            return Response({'detail': '暂无测量数据。'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class AlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        scope_user = scope_user_for_request(self.request)
        queryset = alerts_queryset_for_scope(scope_user)
        device_id = self.request.query_params.get('device_id')
        if device_id:
            queryset = queryset.filter(device__device_id=device_id)
        return queryset


class AlertReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, alert_id):
        scope_user = scope_user_for_request(request)
        alert = get_object_or_404(
            alerts_queryset_for_scope(scope_user),
            id=alert_id,
        )
        serializer = AlertStateUpdateSerializer(instance=alert, data=request.data or {}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AlertSerializer(alert).data, status=status.HTTP_200_OK)


class DashboardOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        payload = build_dashboard_overview(scope_user_for_request(request))
        serializer = DashboardOverviewSerializer(payload)
        return Response(serializer.data)


class MeasurementTrendView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        payload = build_measurement_trends(scope_user_for_request(request))
        serializer = MeasurementTrendSerializer(payload)
        return Response(serializer.data)


class MeasurementLlmInsightView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, measurement_id):
        scope_user = scope_user_for_request(request)
        measurement = get_object_or_404(
            measurements_queryset_for_scope(scope_user).select_related('analysis_result', 'device', 'user'),
            id=measurement_id,
        )
        context = build_measurement_llm_context(measurement, measurement.analysis_result)
        payload = request_llm_insight(context)
        return Response(payload, status=status.HTTP_200_OK)


class AiSettingsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        serializer = AiSettingsSerializer(get_ai_settings())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        settings_obj = get_ai_settings()
        serializer = AiSettingsSerializer(instance=settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AiSettingsSerializer(settings_obj).data, status=status.HTTP_200_OK)
