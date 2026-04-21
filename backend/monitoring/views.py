import copy

from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .llm import (
    build_demo_llm_context,
    build_measurement_llm_context,
    get_ai_settings,
    request_ai_chat,
    request_llm_insight,
)
from .ml import analyze_ppg_samples
from .models import (
    AiSettings,
    AlertEvent,
    Measurement,
    PpgAnalysisRecord,
    PushDeviceRegistration,
    SymptomFeedback,
)
from .serializers import (
    AlertSerializer,
    AlertStateUpdateSerializer,
    AiSettingsSerializer,
    DashboardOverviewSerializer,
    MeasurementBatchIngestSerializer,
    MeasurementTrendSerializer,
    MeasurementSerializer,
    PacketIngestSerializer,
    PpgAnalysisRecordSerializer,
    PpgAnalyzeSerializer,
    PushDeviceRegistrationSerializer,
    SymptomFeedbackSerializer,
)
from .services import (
    alerts_queryset_for_scope,
    build_analysis_history,
    build_analysis_latest,
    build_dashboard_overview,
    build_home_summary,
    build_measurement_chart,
    build_measurement_trends,
    build_period_report,
    devices_queryset_for_scope,
    ingest_packet,
    measurements_queryset_for_scope,
    scope_user_for_request,
)

DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 500


def _get_int_query_param(request, key, default, minimum=0, maximum=None):
    raw_value = request.query_params.get(key)
    if raw_value in {None, ''}:
        return default
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    if maximum is not None:
        value = min(value, maximum)
    return value


def _slice_list_queryset(request, queryset):
    limit = _get_int_query_param(
        request,
        'limit',
        DEFAULT_LIST_LIMIT,
        minimum=1,
        maximum=MAX_LIST_LIMIT,
    )
    offset = _get_int_query_param(request, 'offset', 0, minimum=0)
    return queryset[offset:offset + limit]


class PacketIngestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PacketIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_request_payload = copy.deepcopy(request.data)
        bundle = ingest_packet(
            validated_data=serializer.validated_data,
            raw_payload=raw_request_payload,
            request_user=request.user if request.user.is_authenticated else None,
        )
        return Response(
            MeasurementSerializer(bundle["measurement"]).data,
            status=status.HTTP_201_CREATED,
        )


class PacketBatchIngestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MeasurementBatchIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created_items = []
        raw_items = list(request.data.get("items", []))
        for index, item in enumerate(serializer.validated_data["items"]):
            raw_payload = raw_items[index] if index < len(raw_items) else item
            bundle = ingest_packet(
                validated_data=item,
                raw_payload=raw_payload,
                request_user=request.user,
            )
            created_items.append(MeasurementSerializer(bundle["measurement"]).data)
        return Response(
            {
                "created_count": len(created_items),
                "items": created_items,
            },
            status=status.HTTP_201_CREATED,
        )


class MeasurementListView(generics.ListAPIView):
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        scope_user = scope_user_for_request(self.request)
        queryset = measurements_queryset_for_scope(scope_user).select_related(
            "raw_packet"
        )

        device_id = self.request.query_params.get("device_id")
        start = self.request.query_params.get("start")
        end = self.request.query_params.get("end")

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
        return _slice_list_queryset(self.request, queryset)


class MeasurementLatestView(generics.RetrieveAPIView):
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        scope_user = scope_user_for_request(self.request)
        queryset = measurements_queryset_for_scope(scope_user).select_related(
            "raw_packet"
        )
        device_id = self.request.query_params.get("device_id")
        if device_id:
            queryset = queryset.filter(device__device_id=device_id)
        return queryset.first()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance:
            return Response(
                {"detail": "暂无测量数据。"}, status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class MeasurementDetailView(generics.RetrieveAPIView):
    serializer_class = MeasurementSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "measurement_id"

    def get_object(self):
        scope_user = scope_user_for_request(self.request)
        return get_object_or_404(
            measurements_queryset_for_scope(scope_user).select_related("raw_packet"),
            id=self.kwargs[self.lookup_url_kwarg],
        )


class AlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        scope_user = scope_user_for_request(self.request)
        queryset = alerts_queryset_for_scope(scope_user)
        device_id = self.request.query_params.get("device_id")
        if device_id:
            queryset = queryset.filter(device__device_id=device_id)
        return _slice_list_queryset(self.request, queryset)


class AlertDetailView(generics.RetrieveAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "alert_id"

    def get_object(self):
        scope_user = scope_user_for_request(self.request)
        return get_object_or_404(
            alerts_queryset_for_scope(scope_user), id=self.kwargs[self.lookup_url_kwarg]
        )


class AlertReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, alert_id):
        scope_user = scope_user_for_request(request)
        alert = get_object_or_404(
            alerts_queryset_for_scope(scope_user),
            id=alert_id,
        )
        serializer = AlertStateUpdateSerializer(
            instance=alert, data=request.data or {}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AlertSerializer(alert).data, status=status.HTTP_200_OK)


class AlertReadAllView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.utils import timezone

        # 保留 scope_user_for_request 的原始返回值：admin 无 user_id 查询参数时
        # 返回 None（代表"全部用户"），非 admin 返回 request.user。
        # 之前写成 `or request.user` 会在 admin 场景把 admin 自己塞回 scope_user，
        # 随后 alerts_queryset_for_scope 对 admin 返回 .none()，永远更新 0 条。
        scope_user = scope_user_for_request(request)
        queryset = alerts_queryset_for_scope(scope_user).filter(
            status=AlertEvent.STATUS_UNREAD
        )
        read_at_raw = request.data.get("read_at")
        read_at = (
            parse_datetime(read_at_raw)
            if isinstance(read_at_raw, str) and read_at_raw
            else timezone.now()
        )
        updated = queryset.update(
            status=AlertEvent.STATUS_READ, is_read=True, read_at=read_at
        )
        return Response({"updated_count": updated}, status=status.HTTP_200_OK)


class AlertUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # 同 AlertReadAllView 的说明：保留 scope_user 原始返回，避免 admin
        # 被误塞回成自身作用域后被 alerts_queryset_for_scope 裁为空。
        scope_user = scope_user_for_request(request)
        count = (
            alerts_queryset_for_scope(scope_user)
            .filter(status=AlertEvent.STATUS_UNREAD)
            .count()
        )
        return Response({"unread_count": count}, status=status.HTTP_200_OK)


class HomeSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(build_home_summary(request.user), status=status.HTTP_200_OK)


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


class MeasurementChartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        scope_user = scope_user_for_request(request) or request.user
        metric = request.query_params.get("metric", "heart_rate")
        range_key = request.query_params.get("range", "7d")
        try:
            payload = build_measurement_chart(scope_user, metric, range_key)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)


class AnalysisLatestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        scope_user = scope_user_for_request(request) or request.user
        payload = build_analysis_latest(scope_user)
        if payload is None:
            return Response(
                {"detail": "暂无分析结果。"}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(payload, status=status.HTTP_200_OK)


class AnalysisHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        scope_user = scope_user_for_request(request) or request.user
        limit = min(int(request.query_params.get("limit", 20)), 100)
        return Response(
            {"items": build_analysis_history(scope_user, limit)},
            status=status.HTTP_200_OK,
        )


class MeasurementLlmInsightView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, measurement_id):
        scope_user = scope_user_for_request(request)
        measurement = get_object_or_404(
            measurements_queryset_for_scope(scope_user).select_related(
                "analysis_result", "device", "user"
            ),
            id=measurement_id,
        )
        context = build_measurement_llm_context(
            measurement, measurement.analysis_result
        )
        payload = request_llm_insight(context)
        return Response(payload, status=status.HTTP_200_OK)


class AiChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    MAX_HISTORY_TURNS = 8
    MAX_HISTORY_CHARS = 2000

    def _normalize_history(self, raw_history):
        if not isinstance(raw_history, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in raw_history:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role not in {"user", "assistant"}:
                continue
            if not isinstance(content, str):
                continue
            text = content.strip()
            if not text:
                continue
            normalized.append({"role": role, "content": text[: self.MAX_HISTORY_CHARS]})
        return normalized[-self.MAX_HISTORY_TURNS * 2 :]

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"detail": "message 不能为空。"}, status=status.HTTP_400_BAD_REQUEST
            )
        history = self._normalize_history(request.data.get("history"))
        latest_analysis = build_analysis_latest(request.user)
        trends = build_measurement_trends(request.user)
        unread_count = (
            alerts_queryset_for_scope(request.user)
            .filter(status=AlertEvent.STATUS_UNREAD)
            .count()
        )
        payload = request_ai_chat(
            {
                "user_id": request.user.id,
                "username": request.user.username,
                "latest_analysis": latest_analysis["analysis"]
                if latest_analysis
                else None,
                "trend_preview": trends["daily"],
                "unread_alert_count": unread_count,
            },
            message,
            history=history,
        )
        response_data = {
            "content": payload.get("content", ""),
            "source": payload.get("source"),
            "available": payload.get("available", False),
        }
        if payload.get("source") == "llm" and payload.get("model"):
            response_data["model"] = payload["model"]
        if payload.get("error"):
            response_data["error"] = payload["error"]
        return Response(response_data, status=status.HTTP_200_OK)


class AiSettingsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        serializer = AiSettingsSerializer(get_ai_settings())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        settings_obj = get_ai_settings()
        serializer = AiSettingsSerializer(
            instance=settings_obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            AiSettingsSerializer(settings_obj).data, status=status.HTTP_200_OK
        )


class AiSettingsTestView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AiSettingsSerializer(
            instance=get_ai_settings(), data=request.data or {}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        payload = request_llm_insight(
            build_demo_llm_context(), overrides=serializer.validated_data
        )
        payload["ok"] = payload["source"] in {"template", "llm"} and not payload.get(
            "error"
        )
        return Response(payload, status=status.HTTP_200_OK)


class SymptomFeedbackView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SymptomFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = SymptomFeedback.objects.create(
            user=request.user, **serializer.validated_data
        )
        return Response(
            SymptomFeedbackSerializer(instance).data, status=status.HTTP_201_CREATED
        )


class PushRegisterDeviceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PushDeviceRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance, _ = PushDeviceRegistration.objects.update_or_create(
            device_token=serializer.validated_data["device_token"],
            defaults={
                "user": request.user,
                "provider": serializer.validated_data.get("provider", PushDeviceRegistration.PROVIDER_FCM),
                "platform": serializer.validated_data["platform"],
                "app_version": serializer.validated_data.get("app_version", ""),
                "device_name": serializer.validated_data.get("device_name", ""),
                "is_active": serializer.validated_data.get("is_active", True),
            },
        )
        return Response(
            PushDeviceRegistrationSerializer(instance).data, status=status.HTTP_200_OK
        )


class WeeklyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(build_period_report(request.user, 7), status=status.HTTP_200_OK)


class MonthlyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            build_period_report(request.user, 30), status=status.HTTP_200_OK
        )


class PpgAnalyzeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PpgAnalyzeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user = scope_user_for_request(request) or request.user
        device = get_object_or_404(
            devices_queryset_for_scope(target_user),
            device_id=serializer.validated_data["device_id"],
        )
        analysis = analyze_ppg_samples(
            serializer.validated_data["samples"],
            serializer.validated_data["sample_rate_hz"],
        )
        record = PpgAnalysisRecord.objects.create(
            user=target_user,
            device=device,
            collected_at=serializer.validated_data["collected_at"],
            source=serializer.validated_data["source"],
            sample_rate_hz=serializer.validated_data["sample_rate_hz"],
            window_seconds=serializer.validated_data["window_seconds"],
            sample_count=len(serializer.validated_data["samples"]),
            samples=serializer.validated_data["samples"],
            quality_pass=analysis["quality_pass"],
            quality_score=analysis["quality_score"],
            af_probability=analysis["af_probability"],
            af_label=analysis["af_label"],
            model_version=analysis["model_version"],
            model_source=analysis["model_source"],
            features={
                **analysis["features"],
                "decision_threshold": float(analysis["decision_threshold"]),
            },
        )
        return Response(
            PpgAnalysisRecordSerializer(record).data, status=status.HTTP_201_CREATED
        )
