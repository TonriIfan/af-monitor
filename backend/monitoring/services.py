from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha1
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.location import build_login_location_payload
from devices.models import Device

from .models import AlertEvent, AnalysisResult, Measurement, RawPacket, UploadSession

User = get_user_model()

BATTERY_STATE_MAP = {
    0: '未充电',
    1: '充电中',
    2: '充满',
}

WEAR_STATUS_MAP = {
    0: '未佩戴',
    1: '佩戴',
    2: '充电中不允许采集',
    3: '采集中',
    4: '繁忙不执行',
}

TEMPERATURE_STATUS_MAP = {
    0: '测量中',
    1: '测量完成',
    2: '测量失败并结束',
    3: '繁忙，不执行',
}


@dataclass
class PacketParseResult:
    frame_hex: str
    frame_bytes: list[int]
    command_code: str
    subcommand_code: str
    packet_kind: str
    parsed: dict[str, Any]
    parse_status: str
    parse_error: str


def _to_hex(frame_bytes: list[int]) -> str:
    return ' '.join(f'{value:02X}' for value in frame_bytes)


def _to_bytes(frame_hex: str) -> list[int]:
    return [int(part, 16) for part in frame_hex.strip().split() if part]


def _little_endian_decimal(parts: list[int]) -> Decimal:
    raw_value = int.from_bytes(parts, byteorder='little', signed=False)
    return Decimal(raw_value) / Decimal('100')


def _little_endian_timestamp(parts: list[int]) -> str:
    milliseconds = int.from_bytes(parts, byteorder='little', signed=False)
    dt = timezone.datetime.fromtimestamp(milliseconds / 1000, tz=timezone.get_current_timezone())
    return dt.isoformat()


def parse_packet(payload: dict[str, Any]) -> PacketParseResult:
    frame_bytes = list(payload.get('frame_bytes') or [])
    frame_hex = (payload.get('frame_hex') or '').strip()

    if not frame_bytes and frame_hex:
        frame_bytes = _to_bytes(frame_hex)
    if frame_bytes and not frame_hex:
        frame_hex = _to_hex(frame_bytes)

    if len(frame_bytes) < 4:
        return PacketParseResult(
            frame_hex=frame_hex,
            frame_bytes=frame_bytes,
            command_code='',
            subcommand_code='',
            packet_kind='invalid',
            parsed={},
            parse_status=RawPacket.STATUS_INVALID,
            parse_error='帧长度不足，至少需要 4 个字节。',
        )

    command = frame_bytes[2]
    subcommand = frame_bytes[3]
    command_code = f'0x{command:02X}'
    subcommand_code = f'0x{subcommand:02X}'
    parsed: dict[str, Any] = {}
    packet_kind = 'unknown'
    parse_status = RawPacket.STATUS_PARSED
    parse_error = ''

    if command == 0x12 and subcommand == 0x00 and len(frame_bytes) >= 5:
        packet_kind = 'battery'
        parsed = {'batteryLevel': frame_bytes[4]}
    elif command == 0x12 and subcommand == 0x01 and len(frame_bytes) >= 5:
        packet_kind = 'battery_state'
        parsed = {'batteryState': BATTERY_STATE_MAP.get(frame_bytes[4], '未知状态')}
    elif command == 0x10 and subcommand == 0x00:
        packet_kind = 'time_sync'
        parsed = {'isSyncTime': '时间同步成功'}
    elif command == 0x10 and subcommand == 0x01 and len(frame_bytes) >= 13:
        packet_kind = 'device_time'
        parsed = {
            'ringTime': _little_endian_timestamp(frame_bytes[4:12]),
            'timezone': frame_bytes[12],
        }
    elif command == 0x31 and subcommand == 0x00 and len(frame_bytes) >= 10:
        packet_kind = 'heart_rate'
        parsed = {
            'wearStatusText': WEAR_STATUS_MAP.get(frame_bytes[4], '未知状态'),
            'heartRate': frame_bytes[5],
            'hrv': frame_bytes[6],
            'stress': frame_bytes[7],
            'temperature': float(_little_endian_decimal(frame_bytes[8:10])),
        }
    elif command == 0x32 and subcommand == 0x00 and len(frame_bytes) >= 9:
        packet_kind = 'blood_oxygen'
        parsed = {
            'oxygenWearStatusText': WEAR_STATUS_MAP.get(frame_bytes[4], '未知状态'),
            'oxygenHeartRate': frame_bytes[5],
            'oxygen': frame_bytes[6],
            'oxygenTemperature': float(_little_endian_decimal(frame_bytes[7:9])),
        }
    elif command == 0x34 and subcommand == 0x00 and len(frame_bytes) >= 7:
        packet_kind = 'temperature'
        parsed = {
            'StatusText': TEMPERATURE_STATUS_MAP.get(frame_bytes[4], '未知状态'),
            'TempTest': float(_little_endian_decimal(frame_bytes[5:7])),
        }
    elif command == 0x32 and subcommand == 0xFF and len(frame_bytes) >= 5:
        packet_kind = 'blood_oxygen_complete'
        parsed = {'oxygenWearStatusText': '采集完成' if frame_bytes[4] == 0x64 else '未知状态'}
    else:
        packet_kind = 'unsupported'
        parse_status = RawPacket.STATUS_UNSUPPORTED
        parse_error = f'暂不支持的命令: {command_code} {subcommand_code}'

    return PacketParseResult(
        frame_hex=frame_hex,
        frame_bytes=frame_bytes,
        command_code=command_code,
        subcommand_code=subcommand_code,
        packet_kind=packet_kind,
        parsed=parsed,
        parse_status=parse_status,
        parse_error=parse_error,
    )


def _measurement_fields(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        'battery_level': parsed.get('batteryLevel'),
        'battery_state': parsed.get('batteryState', ''),
        'heart_rate': parsed.get('heartRate'),
        'hrv': parsed.get('hrv'),
        'stress': parsed.get('stress'),
        'oxygen': parsed.get('oxygen'),
        'oxygen_heart_rate': parsed.get('oxygenHeartRate'),
        'temperature': parsed.get('temperature'),
        'oxygen_temperature': parsed.get('oxygenTemperature'),
        'body_temperature': parsed.get('TempTest'),
        'wear_status': parsed.get('wearStatusText', ''),
        'oxygen_wear_status': parsed.get('oxygenWearStatusText', ''),
        'measurement_status': parsed.get('StatusText', ''),
        'is_complete': parsed.get('oxygenWearStatusText') == '采集完成',
    }


def analyze_measurement(measurement: Measurement) -> dict[str, Any]:
    triggers: list[str] = []
    labels: list[str] = []
    score = Decimal('0.00')
    worn = measurement.wear_status in {'佩戴', '采集中'} or measurement.oxygen_wear_status in {'佩戴', '采集中'}

    if measurement.heart_rate and worn and measurement.heart_rate > 110:
        triggers.append('tachycardia')
        score += Decimal('0.35')
    if measurement.heart_rate and worn and measurement.heart_rate < 50:
        triggers.append('bradycardia')
        score += Decimal('0.25')
    if measurement.hrv and measurement.hrv >= 35:
        triggers.append('hrv_instability')
        score += Decimal('0.20')
    if measurement.stress and measurement.stress >= 80:
        triggers.append('high_stress')
        score += Decimal('0.10')
    if measurement.oxygen and measurement.oxygen < 95:
        triggers.append('low_oxygen')
        score += Decimal('0.25')
    if measurement.temperature and measurement.temperature >= Decimal('37.80'):
        triggers.append('fever')
        score += Decimal('0.10')
    if measurement.body_temperature and measurement.body_temperature >= Decimal('37.80'):
        triggers.append('fever')
        score += Decimal('0.10')

    if {'tachycardia', 'hrv_instability', 'low_oxygen'}.issubset(set(triggers)):
        triggers.append('suspected_arrhythmia_cluster')
        score += Decimal('0.20')

    score = min(score, Decimal('0.99'))
    if score >= Decimal('0.80'):
        risk_level = AlertEvent.LEVEL_CRITICAL
        labels.append('高危异常心律风险')
    elif score >= Decimal('0.55'):
        risk_level = AlertEvent.LEVEL_HIGH
        labels.append('较高异常心律风险')
    elif score >= Decimal('0.30'):
        risk_level = AlertEvent.LEVEL_MODERATE
        labels.append('中等异常心律风险')
    else:
        risk_level = AlertEvent.LEVEL_LOW
        labels.append('低风险')

    should_alert = risk_level in {AlertEvent.LEVEL_HIGH, AlertEvent.LEVEL_CRITICAL}
    summary = '未发现明显异常。'
    if triggers:
        summary = f"命中规则: {', '.join(triggers)}。"

    return {
        'algorithm_version': 'rules-v1',
        'risk_level': risk_level,
        'risk_score': score.quantize(Decimal('0.01')),
        'labels': labels,
        'triggers': triggers,
        'summary': summary,
        'should_alert': should_alert,
    }


def _resolve_client_time(validated_data: dict[str, Any]):
    client_time = validated_data['client_time']
    if isinstance(client_time, str):
        parsed = parse_datetime(client_time)
        if parsed is not None:
            return parsed
    return client_time


def _resolve_user(device: Device, request_user):
    if request_user is not None:
        return request_user
    binding = device.bindings.filter(is_active=True).select_related('user').first()
    return binding.user if binding else None


def _get_or_create_upload_session(device: Device, user, validated_data: dict[str, Any]):
    session_key = validated_data.get('session_key')
    if not session_key:
        return None
    client_time = _resolve_client_time(validated_data)
    session, _ = UploadSession.objects.get_or_create(
        session_key=session_key,
        defaults={
            'device': device,
            'user': user,
            'source': validated_data.get('source', 'wechat-miniapp'),
            'client_started_at': client_time,
            'last_client_time': client_time,
            'packet_count': 0,
        },
    )
    session.last_client_time = client_time
    session.packet_count += 1
    session.save(update_fields=['last_client_time', 'packet_count', 'updated_at'])
    return session


def _build_dedupe_key(measurement: Measurement, analysis_result: AnalysisResult) -> str:
    bucket = measurement.measured_at.astimezone(timezone.get_current_timezone()).strftime('%Y%m%d%H') + str(
        measurement.measured_at.minute // 10
    )
    fingerprint = {
        'device_id': measurement.device.device_id,
        'bucket': bucket,
        'triggers': analysis_result.triggers,
        'heart_rate': measurement.heart_rate,
        'oxygen': measurement.oxygen,
        'hrv': measurement.hrv,
        'stress': measurement.stress,
    }
    return sha1(repr(fingerprint).encode('utf-8')).hexdigest()


def maybe_create_alert(measurement: Measurement, analysis_result: AnalysisResult):
    if not analysis_result.should_alert:
        return None

    dedupe_key = _build_dedupe_key(measurement, analysis_result)
    recent_window = measurement.measured_at - timezone.timedelta(minutes=10)
    existing = AlertEvent.objects.filter(
        device=measurement.device,
        dedupe_key=dedupe_key,
        created_at__gte=recent_window,
        status=AlertEvent.STATUS_UNREAD,
    ).first()
    if existing:
        return existing

    title = '疑似房颤风险预警'
    if analysis_result.risk_level == AlertEvent.LEVEL_CRITICAL:
        title = '高危房颤风险预警'

    return AlertEvent.objects.create(
        device=measurement.device,
        user=measurement.user,
        measurement=measurement,
        analysis_result=analysis_result,
        level=analysis_result.risk_level,
        title=title,
        message=analysis_result.summary,
        trigger_codes=analysis_result.triggers,
        dedupe_key=dedupe_key,
    )


@transaction.atomic
def ingest_packet(validated_data: dict[str, Any], raw_payload: dict[str, Any], request_user=None):
    device, _ = Device.objects.get_or_create(
        device_id=validated_data['device_id'],
        defaults={
            'name': validated_data['device_id'],
            'source': validated_data.get('source', 'wechat-miniapp'),
        },
    )
    user = _resolve_user(device, request_user)
    upload_session = _get_or_create_upload_session(device, user, validated_data)
    parse_result = parse_packet(validated_data['payload'])
    client_time = _resolve_client_time(validated_data)

    device.source = validated_data.get('source', device.source)
    device.last_seen_at = timezone.now()
    device.save(update_fields=['source', 'last_seen_at', 'updated_at'])

    raw_packet = RawPacket.objects.create(
        device=device,
        user=user,
        upload_session=upload_session,
        source=validated_data.get('source', 'wechat-miniapp'),
        client_time=client_time,
        raw_payload=deepcopy(raw_payload),
        frame_hex=parse_result.frame_hex,
        frame_bytes=parse_result.frame_bytes,
        command_code=parse_result.command_code,
        subcommand_code=parse_result.subcommand_code,
        packet_kind=parse_result.packet_kind,
        parse_status=parse_result.parse_status,
        parse_error=parse_result.parse_error,
    )

    measurement = Measurement.objects.create(
        raw_packet=raw_packet,
        device=device,
        user=user,
        measured_at=client_time,
        packet_kind=parse_result.packet_kind,
        parsed=parse_result.parsed,
        **_measurement_fields(parse_result.parsed),
    )

    analysis_payload = analyze_measurement(measurement)
    analysis_result = AnalysisResult.objects.create(
        measurement=measurement,
        raw_packet=raw_packet,
        device=device,
        user=user,
        **analysis_payload,
    )
    maybe_create_alert(measurement, analysis_result)

    return {
        'raw_packet': raw_packet,
        'measurement': measurement,
        'analysis_result': analysis_result,
    }


def get_device_status_payload(device: Device, user) -> dict[str, Any]:
    latest = device.measurements.select_related('raw_packet', 'analysis_result').first()
    latest_measurement = None
    if latest:
        latest_measurement = {
            'id': latest.id,
            'measured_at': latest.measured_at,
            'packet_kind': latest.packet_kind,
            'parsed': latest.parsed,
            'analysis': {
                'risk_level': latest.analysis_result.risk_level,
                'risk_score': float(latest.analysis_result.risk_score),
                'summary': latest.analysis_result.summary,
            },
        }

    return {
        'device_id': device.device_id,
        'name': device.name,
        'source': device.source,
        'last_seen_at': device.last_seen_at,
        'unread_alerts': device.alerts.filter(status=AlertEvent.STATUS_UNREAD).count(),
        'latest_measurement': latest_measurement,
    }


def scope_user_for_request(request):
    if getattr(request.user, 'role', None) == User.Role.ADMIN:
        requested_user_id = request.query_params.get('user_id') or request.data.get('user_id')
        if requested_user_id:
            return get_object_or_404(User, pk=requested_user_id)
        return None
    return request.user


def measurements_queryset_for_scope(scope_user=None):
    queryset = Measurement.objects.select_related('device', 'analysis_result', 'user')
    if scope_user is None:
        return queryset
    return queryset.filter(device__bindings__user=scope_user, device__bindings__is_active=True).distinct()


def alerts_queryset_for_scope(scope_user=None):
    queryset = AlertEvent.objects.select_related('device', 'measurement', 'analysis_result', 'user')
    if scope_user is None:
        return queryset
    return queryset.filter(device__bindings__user=scope_user, device__bindings__is_active=True).distinct()


def devices_queryset_for_scope(scope_user=None):
    queryset = Device.objects.all()
    if scope_user is None:
        return queryset.distinct()
    return queryset.filter(bindings__user=scope_user, bindings__is_active=True).distinct()


def build_dashboard_overview(scope_user=None) -> dict[str, Any]:
    base_measurements = measurements_queryset_for_scope(scope_user)
    base_alerts = alerts_queryset_for_scope(scope_user)
    devices = devices_queryset_for_scope(scope_user)
    user_queryset = (
        User.objects.all()
        if scope_user is None
        else User.objects.filter(pk=scope_user.pk)
    ).annotate(
        device_count=Count('device_bindings__device', filter=Q(device_bindings__is_active=True), distinct=True),
        measurement_count=Count('measurements', distinct=True),
        unread_alert_count=Count('alerts', filter=Q(alerts__status='unread'), distinct=True),
    ).order_by('-is_staff', 'username')

    risk_distribution = list(
        base_measurements.values('analysis_result__risk_level')
        .annotate(total=Count('id'))
        .order_by('analysis_result__risk_level')
    )

    latest_measurements = [
        {
            'id': item.id,
            'device_id': item.device.device_id,
            'user_id': item.user_id,
            'username': item.user.username if item.user else '',
            'measured_at': item.measured_at,
            'packet_kind': item.packet_kind,
            'parsed': item.parsed,
            'risk_level': item.analysis_result.risk_level if hasattr(item, 'analysis_result') else None,
        }
        for item in base_measurements[:6]
    ]
    latest_alerts = [
        {
            'id': alert.id,
            'device_id': alert.device.device_id,
            'user_id': alert.user_id,
            'username': alert.user.username if alert.user else '',
            'level': alert.level,
            'title': alert.title,
            'status': alert.status,
            'created_at': alert.created_at,
        }
        for alert in base_alerts[:6]
    ]

    return {
        'counts': {
            'devices': devices.count(),
            'measurements': base_measurements.count(),
            'alerts': base_alerts.count(),
            'unread_alerts': base_alerts.filter(status=AlertEvent.STATUS_UNREAD).count(),
        },
        'user_summaries': [
            {
                'id': item.id,
                'username': item.username,
                'role': item.role,
                'last_login_ip': item.last_login_ip,
                'last_login_location': build_login_location_payload(item),
                'device_count': item.device_count,
                'measurement_count': item.measurement_count,
                'unread_alert_count': item.unread_alert_count,
            }
            for item in user_queryset
        ],
        'risk_distribution': [
            {
                'risk_level': item['analysis_result__risk_level'] or 'unknown',
                'total': item['total'],
            }
            for item in risk_distribution
        ],
        'latest_measurements': latest_measurements,
        'latest_alerts': latest_alerts,
    }
