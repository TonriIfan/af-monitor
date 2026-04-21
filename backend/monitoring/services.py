from __future__ import annotations

from copy import deepcopy
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha1
from statistics import mean
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.location import build_login_location_payload
from devices.models import Device, DeviceBinding

from .ml import analyze_structured_measurement_window
from .models import (
    AlertEvent,
    AlertPushDelivery,
    AnalysisResult,
    Measurement,
    PushDeviceRegistration,
    RawPacket,
    UploadSession,
)
from .push import PushSendResult, get_push_provider

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

TRIGGER_LABEL_MAP = {
    'realtime_tachycardia': '当前心率偏快',
    'realtime_bradycardia': '当前心率偏慢',
    'realtime_hrv_instability': '心率变异性波动偏大',
    'realtime_high_stress': '压力指标偏高',
    'realtime_low_oxygen': '血氧偏低',
    'realtime_fever': '体温偏高',
    'realtime_arrhythmia_cluster': '心率、血氧与变异性同时异常',
    'window_repeated_tachycardia_30m': '近 30 分钟多次心率偏快',
    'window_repeated_low_oxygen_30m': '近 30 分钟多次血氧偏低',
    'window_repeated_hrv_instability_30m': '近 30 分钟多次心率变异性异常',
    'window_repeated_high_risk_24h': '近 24 小时多次出现高风险记录',
    'baseline_heart_rate_above_personal_baseline': '心率明显高于个人近期基线',
    'baseline_oxygen_below_personal_baseline': '血氧低于个人近期基线',
    'baseline_hrv_above_personal_baseline': '心率变异性高于个人近期基线',
    'baseline_temperature_above_personal_baseline': '体温高于个人近期基线',
    'ml_structured_af_positive': '结构化模型提示房颤风险',
    'ml_structured_af_watch': '结构化模型提示需要持续观察',
    'ml_structured_af_negative': '结构化模型暂未提示房颤阳性',
    'context_unstable_wear_state': '佩戴状态不稳定，结果需谨慎解释',
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


def _metric_samples(queryset, field_name: str, limit: int = 20) -> list[float]:
    values = list(
        queryset.exclude(**{f'{field_name}__isnull': True}).values_list(field_name, flat=True)[:limit]
    )
    samples: list[float] = []
    for value in values:
        try:
            samples.append(float(value))
        except (TypeError, ValueError):
            continue
    return samples


def _history_queryset(measurement: Measurement):
    queryset = Measurement.objects.filter(device=measurement.device).exclude(pk=measurement.pk)
    if measurement.user_id:
        queryset = queryset.filter(user_id=measurement.user_id)
    return queryset.order_by('-measured_at')


def _window_queryset(queryset, measurement: Measurement, minutes: int):
    window_start = measurement.measured_at - timezone.timedelta(minutes=minutes)
    return queryset.filter(measured_at__gte=window_start)


def _build_realtime_flags(measurement: Measurement, worn: bool) -> tuple[list[str], Decimal]:
    flags: list[str] = []
    score = Decimal('0.00')

    if measurement.heart_rate and worn and measurement.heart_rate > 110:
        flags.append('realtime_tachycardia')
        score += Decimal('0.28')
    if measurement.heart_rate and worn and measurement.heart_rate < 50:
        flags.append('realtime_bradycardia')
        score += Decimal('0.20')
    if measurement.hrv and measurement.hrv >= 35:
        flags.append('realtime_hrv_instability')
        score += Decimal('0.16')
    if measurement.stress and measurement.stress >= 80:
        flags.append('realtime_high_stress')
        score += Decimal('0.08')
    if measurement.oxygen and measurement.oxygen < 95:
        flags.append('realtime_low_oxygen')
        score += Decimal('0.20')

    current_temp = measurement.temperature or measurement.body_temperature
    if current_temp and current_temp >= Decimal('37.80'):
        flags.append('realtime_fever')
        score += Decimal('0.06')

    if {'realtime_tachycardia', 'realtime_hrv_instability', 'realtime_low_oxygen'}.issubset(set(flags)):
        flags.append('realtime_arrhythmia_cluster')
        score += Decimal('0.14')

    return flags, score


def _build_window_flags(measurement: Measurement, history_queryset) -> tuple[list[str], Decimal, dict[str, Any]]:
    flags: list[str] = []
    score = Decimal('0.00')
    recent_30m = _window_queryset(history_queryset, measurement, 30)
    recent_24h = _window_queryset(history_queryset, measurement, 24 * 60)

    hr_count = recent_30m.filter(heart_rate__gt=110).count()
    oxygen_count = recent_30m.filter(oxygen__lt=95).count()
    hrv_count = recent_30m.filter(hrv__gte=35).count()
    alert_count = recent_24h.filter(analysis_result__should_alert=True).count()

    if measurement.heart_rate and measurement.heart_rate > 110:
        hr_count += 1
    if measurement.oxygen and measurement.oxygen < 95:
        oxygen_count += 1
    if measurement.hrv and measurement.hrv >= 35:
        hrv_count += 1

    if hr_count >= 3:
        flags.append('window_repeated_tachycardia_30m')
        score += Decimal('0.16')
    if oxygen_count >= 2:
        flags.append('window_repeated_low_oxygen_30m')
        score += Decimal('0.14')
    if hrv_count >= 3:
        flags.append('window_repeated_hrv_instability_30m')
        score += Decimal('0.10')
    if alert_count >= 2:
        flags.append('window_repeated_high_risk_24h')
        score += Decimal('0.12')

    window_stats = {
        'tachycardia_count_30m': hr_count,
        'low_oxygen_count_30m': oxygen_count,
        'hrv_instability_count_30m': hrv_count,
        'high_risk_count_24h': alert_count,
    }
    return flags, score, window_stats


def _build_baseline_flags(measurement: Measurement, history_queryset) -> tuple[list[str], Decimal, dict[str, Any]]:
    flags: list[str] = []
    score = Decimal('0.00')
    baseline_queryset = history_queryset.filter(measured_at__gte=measurement.measured_at - timezone.timedelta(days=7))

    baseline_heart_rate = _metric_samples(baseline_queryset, 'heart_rate')
    baseline_hrv = _metric_samples(baseline_queryset, 'hrv')
    baseline_oxygen = _metric_samples(baseline_queryset, 'oxygen')
    baseline_temperature = _metric_samples(baseline_queryset, 'temperature')

    baselines = {
        'heart_rate': round(mean(baseline_heart_rate), 2) if baseline_heart_rate else None,
        'hrv': round(mean(baseline_hrv), 2) if baseline_hrv else None,
        'oxygen': round(mean(baseline_oxygen), 2) if baseline_oxygen else None,
        'temperature': round(mean(baseline_temperature), 2) if baseline_temperature else None,
    }

    if baselines['heart_rate'] is not None and measurement.heart_rate:
        if float(measurement.heart_rate) - baselines['heart_rate'] >= 15:
            flags.append('baseline_heart_rate_above_personal_baseline')
            score += Decimal('0.12')
    if baselines['oxygen'] is not None and measurement.oxygen:
        if baselines['oxygen'] - float(measurement.oxygen) >= 3:
            flags.append('baseline_oxygen_below_personal_baseline')
            score += Decimal('0.12')
    if baselines['hrv'] is not None and measurement.hrv:
        if float(measurement.hrv) - baselines['hrv'] >= 10:
            flags.append('baseline_hrv_above_personal_baseline')
            score += Decimal('0.08')

    current_temp = measurement.temperature or measurement.body_temperature
    if baselines['temperature'] is not None and current_temp:
        if float(current_temp) - baselines['temperature'] >= 0.5:
            flags.append('baseline_temperature_above_personal_baseline')
            score += Decimal('0.05')

    return flags, score, baselines


def _structured_ml_unavailable(skip_reason: str) -> dict[str, Any]:
    return {
        'enabled': True,
        'available': False,
        'model_name': '',
        'model_version': '',
        'probability': 0.0,
        'decision_threshold': 0.0,
        'label': False,
        'feature_source': 'measurement_window',
        'skip_reason': skip_reason,
        'features': {},
    }


def _build_structured_ml_analysis(measurement: Measurement, history_queryset) -> dict[str, Any]:
    if measurement.heart_rate is None:
        return _structured_ml_unavailable('current_heart_rate_missing')

    lookback_minutes = settings.STRUCTURED_AF_LOOKBACK_MINUTES
    window_measurements = list(
        _window_queryset(history_queryset, measurement, lookback_minutes)
        .exclude(heart_rate__isnull=True)
        .order_by('measured_at')
    )
    window_measurements.append(measurement)
    duration_seconds = float(lookback_minutes * 60)
    return analyze_structured_measurement_window(window_measurements, duration_seconds)


def _risk_from_score(score: Decimal) -> tuple[str, str]:
    if score >= Decimal('0.80'):
        return AlertEvent.LEVEL_CRITICAL, '高危异常心律风险'
    if score >= Decimal('0.50'):
        return AlertEvent.LEVEL_HIGH, '较高异常心律风险'
    if score >= Decimal('0.30'):
        return AlertEvent.LEVEL_MODERATE, '中等异常心律风险'
    return AlertEvent.LEVEL_LOW, '低风险'


def _rule_summary_parts(realtime_flags: list[str], window_flags: list[str], baseline_flags: list[str]) -> list[str]:
    summary_parts = []
    if realtime_flags:
        summary_parts.append(f'实时异常: {_trigger_labels_text(realtime_flags)}')
    if window_flags:
        summary_parts.append(f'时间窗异常: {_trigger_labels_text(window_flags)}')
    if baseline_flags:
        summary_parts.append(f'基线偏移: {_trigger_labels_text(baseline_flags)}')
    return summary_parts


def trigger_label(code: str) -> str:
    return TRIGGER_LABEL_MAP.get(code, code)


def trigger_labels(codes: list[str]) -> list[str]:
    return [trigger_label(code) for code in codes]


def _trigger_labels_text(codes: list[str]) -> str:
    return '、'.join(trigger_labels(codes))


def _ml_score_from_probability(probability: Decimal, threshold: Decimal) -> Decimal:
    if probability >= Decimal('0.85'):
        return Decimal('0.88')
    if probability >= threshold:
        return max(Decimal('0.62'), min(Decimal('0.84'), probability))
    if probability >= max(Decimal('0.00'), threshold - Decimal('0.15')):
        return max(Decimal('0.34'), min(Decimal('0.49'), probability))
    return min(Decimal('0.29'), probability)


def analyze_measurement(measurement: Measurement) -> dict[str, Any]:
    labels: list[str] = []
    worn = measurement.wear_status in {'佩戴', '采集中'} or measurement.oxygen_wear_status in {'佩戴', '采集中'}
    history_queryset = _history_queryset(measurement)
    realtime_flags, realtime_score = _build_realtime_flags(measurement, worn)
    window_flags, window_score, window_stats = _build_window_flags(measurement, history_queryset)
    baseline_flags, baseline_score, baselines = _build_baseline_flags(measurement, history_queryset)
    ml_analysis = _build_structured_ml_analysis(measurement, history_queryset)

    if ml_analysis.get('available'):
        probability = Decimal(str(ml_analysis.get('probability') or 0))
        threshold = Decimal(str(ml_analysis.get('decision_threshold') or 0.5))
        ml_summary = f'结构化 ML 房颤概率: {probability}'
        score = _ml_score_from_probability(probability, threshold)
        if not worn:
            score = max(Decimal('0.00'), score - Decimal('0.10'))

        risk_level, risk_label = _risk_from_score(score)
        labels.append(risk_label)
        triggers = ['ml_structured_af_negative']
        if ml_analysis.get('label'):
            triggers = ['ml_structured_af_positive']
            labels.append('机器学习提示房颤风险')
        elif score >= Decimal('0.30'):
            triggers = ['ml_structured_af_watch']
            labels.append('机器学习提示需持续观察')

        if not worn:
            triggers.append('context_unstable_wear_state')
            labels.append('佩戴状态不稳定，结果需谨慎解释')

        if realtime_flags or window_flags or baseline_flags:
            labels.append('规则引擎提供辅助解释')

        should_alert = risk_level in {AlertEvent.LEVEL_HIGH, AlertEvent.LEVEL_CRITICAL}
        summary_parts = [ml_summary]
        summary_parts.extend(_rule_summary_parts(realtime_flags, window_flags, baseline_flags))
        summary_parts.append(f'综合命中: {_trigger_labels_text(triggers)}')
    else:
        triggers = realtime_flags + window_flags + baseline_flags
        score = realtime_score + window_score + baseline_score
        if not worn:
            triggers.append('context_unstable_wear_state')
            score = max(Decimal('0.00'), score - Decimal('0.10'))

        score = min(score, Decimal('0.99'))
        risk_level, risk_label = _risk_from_score(score)
        labels.append(risk_label)
        if window_flags:
            labels.append('存在连续时间窗异常')
        if baseline_flags:
            labels.append('存在个人基线偏移')
        if not worn:
            labels.append('佩戴状态不稳定，结果需谨慎解释')
        labels.append('机器学习暂不可用，已使用规则引擎兜底')

        should_alert = risk_level in {AlertEvent.LEVEL_HIGH, AlertEvent.LEVEL_CRITICAL}
        summary_parts = _rule_summary_parts(realtime_flags, window_flags, baseline_flags)
        if not summary_parts:
            summary_parts.append('未发现明显异常。')
        if triggers:
            summary_parts.append(f'综合命中: {_trigger_labels_text(triggers)}')

    return {
        'algorithm_version': 'structured-ml-primary-v1',
        'risk_level': risk_level,
        'risk_score': score.quantize(Decimal('0.01')),
        'labels': labels,
        'triggers': triggers,
        'summary': '；'.join(summary_parts),
        'should_alert': should_alert,
        'details': {
            'realtime_flags': realtime_flags,
            'window_flags': window_flags,
            'baseline_flags': baseline_flags,
            'window_stats': window_stats,
            'baselines': baselines,
            'wearing_effective': worn,
            'ml': ml_analysis,
        },
    }


def _resolve_client_time(validated_data: dict[str, Any]):
    client_time = validated_data['client_time']
    if isinstance(client_time, str):
        parsed = parse_datetime(client_time)
        if parsed is not None:
            return parsed
    return client_time


def _resolve_user(device: Device, request_user, validated_data: dict[str, Any]):
    requested_user_id = validated_data.get('user_id')
    if request_user is not None and getattr(request_user, 'role', None) == User.Role.ADMIN and requested_user_id:
        return get_object_or_404(User.objects.exclude(role=User.Role.ADMIN), pk=requested_user_id)
    if request_user is not None:
        return request_user
    binding = device.bindings.filter(is_active=True).select_related('user').first()
    return binding.user if binding else None


def _ensure_simulator_binding(device: Device, user, validated_data: dict[str, Any]):
    if not user or getattr(user, 'role', None) == User.Role.ADMIN:
        return
    if validated_data.get('source') != 'console-simulator' or not validated_data.get('user_id'):
        return

    DeviceBinding.objects.filter(device=device, is_active=True).exclude(user=user).update(
        is_active=False,
        unbound_at=timezone.now(),
    )
    DeviceBinding.objects.get_or_create(
        user=user,
        device=device,
        is_active=True,
        defaults={'alias': '控制台测试设备'},
    )


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


def build_alert_push_payload(alert: AlertEvent) -> dict[str, Any]:
    measurement_id = alert.measurement_id or 0
    return {
        'notification': {
            'title': alert.title,
            'body': alert.message,
        },
        'data': {
            'type': 'alert',
            'alert_id': str(alert.id),
            'level': alert.level,
            'device_id': alert.device.device_id,
            'measurement_id': str(measurement_id),
            'created_at': alert.created_at.isoformat(),
            'route': f'/alerts/{alert.id}',
        },
    }


def enqueue_alert_push_deliveries(alert: AlertEvent) -> int:
    if not alert.user_id:
        return 0

    registrations = PushDeviceRegistration.objects.filter(user_id=alert.user_id, is_active=True)
    created_count = 0
    for registration in registrations:
        _, created = AlertPushDelivery.objects.get_or_create(
            alert=alert,
            registration=registration,
            defaults={
                'user_id': alert.user_id,
                'provider': registration.provider,
                'platform': registration.platform,
                'device_token': registration.device_token,
                'max_attempts': settings.ALERT_PUSH_MAX_ATTEMPTS,
            },
        )
        if created:
            created_count += 1
    return created_count


def _delivery_retry_delay_minutes(attempts: int) -> int:
    schedule = [1, 5, 15]
    index = max(0, min(attempts - 1, len(schedule) - 1))
    return schedule[index]


def dispatch_alert_push_delivery(delivery: AlertPushDelivery, provider=None) -> AlertPushDelivery:
    now = timezone.now()
    registration = delivery.registration
    if registration is None:
        delivery.status = AlertPushDelivery.STATUS_SKIPPED
        delivery.last_error_code = 'registration_missing'
        delivery.last_error = '关联的推送设备已不存在。'
        delivery.next_attempt_at = now
        delivery.save(
            update_fields=[
                'status',
                'last_error_code',
                'last_error',
                'next_attempt_at',
                'updated_at',
            ]
        )
        return delivery

    if not registration.is_active:
        delivery.status = AlertPushDelivery.STATUS_SKIPPED
        delivery.last_error_code = 'registration_inactive'
        delivery.last_error = '推送设备已停用。'
        delivery.next_attempt_at = now
        delivery.save(
            update_fields=[
                'status',
                'last_error_code',
                'last_error',
                'next_attempt_at',
                'updated_at',
            ]
        )
        return delivery

    if provider is None:
        provider = get_push_provider(delivery.provider)

    payload = build_alert_push_payload(delivery.alert)
    result: PushSendResult = provider.send_alert(delivery, payload)
    delivery.attempts += 1

    if result.success:
        delivery.status = AlertPushDelivery.STATUS_SENT
        delivery.provider_message_id = result.message_id
        delivery.last_error_code = ''
        delivery.last_error = ''
        delivery.sent_at = now
        delivery.next_attempt_at = now
        delivery.save(
            update_fields=[
                'status',
                'attempts',
                'provider_message_id',
                'last_error_code',
                'last_error',
                'sent_at',
                'next_attempt_at',
                'updated_at',
            ]
        )
        return delivery

    delivery.last_error_code = result.error_code
    delivery.last_error = result.error_message
    if result.invalid_token:
        registration.is_active = False
        registration.save(update_fields=['is_active'])
        delivery.status = AlertPushDelivery.STATUS_FAILED
        delivery.next_attempt_at = now
    elif result.retryable and delivery.attempts < delivery.max_attempts:
        delivery.status = AlertPushDelivery.STATUS_PENDING
        delivery.next_attempt_at = now + timezone.timedelta(
            minutes=_delivery_retry_delay_minutes(delivery.attempts)
        )
    elif result.error_code == 'fcm_disabled':
        delivery.status = AlertPushDelivery.STATUS_SKIPPED
        delivery.next_attempt_at = now
    else:
        delivery.status = AlertPushDelivery.STATUS_FAILED
        delivery.next_attempt_at = now

    delivery.save(
        update_fields=[
            'status',
            'attempts',
            'last_error_code',
            'last_error',
            'next_attempt_at',
            'updated_at',
        ]
    )
    return delivery


def dispatch_pending_alert_pushes(limit: int = 100, provider=None) -> dict[str, int]:
    queryset = (
        AlertPushDelivery.objects.select_related('alert__device', 'registration')
        .filter(
            status=AlertPushDelivery.STATUS_PENDING,
            next_attempt_at__lte=timezone.now(),
        )
        .order_by('next_attempt_at', 'id')[:limit]
    )

    summary = {
        'processed': 0,
        'sent': 0,
        'failed': 0,
        'skipped': 0,
        'pending': 0,
    }
    for delivery in queryset:
        dispatch_alert_push_delivery(delivery, provider=provider)
        summary['processed'] += 1
        summary[delivery.status] += 1
    return summary


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

    alert = AlertEvent.objects.create(
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
    transaction.on_commit(lambda: enqueue_alert_push_deliveries(alert))
    return alert


@transaction.atomic
def ingest_packet(validated_data: dict[str, Any], raw_payload: dict[str, Any], request_user=None):
    device, _ = Device.objects.get_or_create(
        device_id=validated_data['device_id'],
        defaults={
            'name': validated_data['device_id'],
            'source': validated_data.get('source', 'wechat-miniapp'),
        },
    )
    user = _resolve_user(device, request_user, validated_data)
    _ensure_simulator_binding(device, user, validated_data)
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
        return queryset.exclude(user__role=User.Role.ADMIN)
    if getattr(scope_user, 'role', None) == User.Role.ADMIN:
        return queryset.none()
    return queryset.filter(device__bindings__user=scope_user, device__bindings__is_active=True).distinct()


def alerts_queryset_for_scope(scope_user=None):
    queryset = AlertEvent.objects.select_related(
        'device', 'measurement', 'analysis_result', 'user'
    ).prefetch_related('push_deliveries')
    if scope_user is None:
        return queryset.exclude(user__role=User.Role.ADMIN)
    if getattr(scope_user, 'role', None) == User.Role.ADMIN:
        return queryset.none()
    return queryset.filter(device__bindings__user=scope_user, device__bindings__is_active=True).distinct()


def devices_queryset_for_scope(scope_user=None):
    queryset = Device.objects.all()
    if scope_user is None:
        return queryset.filter(bindings__user__role=User.Role.USER, bindings__is_active=True).distinct()
    if getattr(scope_user, 'role', None) == User.Role.ADMIN:
        return queryset.none()
    return queryset.filter(bindings__user=scope_user, bindings__is_active=True).distinct()


def build_dashboard_overview(scope_user=None) -> dict[str, Any]:
    base_measurements = measurements_queryset_for_scope(scope_user)
    base_alerts = alerts_queryset_for_scope(scope_user)
    devices = devices_queryset_for_scope(scope_user)
    user_queryset = (
        User.objects.filter(role=User.Role.USER)
        if scope_user is None
        else User.objects.filter(pk=scope_user.pk).exclude(role=User.Role.ADMIN)
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


def _trend_bucket_template(label: str) -> dict[str, Any]:
    return {
        'label': label,
        'measurement_count': 0,
        'high_risk_count': 0,
        'alert_count': 0,
        'heart_rate_values': [],
        'oxygen_values': [],
    }


def _finalize_trend_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    heart_rate_values = bucket.pop('heart_rate_values')
    oxygen_values = bucket.pop('oxygen_values')
    bucket['avg_heart_rate'] = round(mean(heart_rate_values), 2) if heart_rate_values else None
    bucket['avg_oxygen'] = round(mean(oxygen_values), 2) if oxygen_values else None
    return bucket


def build_measurement_trends(scope_user=None) -> dict[str, Any]:
    queryset = (
        measurements_queryset_for_scope(scope_user)
        .select_related('analysis_result')
        .filter(measured_at__gte=timezone.now() - timezone.timedelta(days=56))
    )
    alerts = alerts_queryset_for_scope(scope_user).filter(created_at__gte=timezone.now() - timezone.timedelta(days=56))

    daily_buckets: dict[str, dict[str, Any]] = {}
    weekly_buckets: dict[str, dict[str, Any]] = {}

    for day_offset in range(6, -1, -1):
        day = (timezone.localtime(timezone.now()) - timezone.timedelta(days=day_offset)).date()
        label = day.isoformat()
        daily_buckets[label] = _trend_bucket_template(label)

    for week_offset in range(7, -1, -1):
        day = (timezone.localtime(timezone.now()) - timezone.timedelta(days=7 * week_offset)).date()
        week_start = day - timezone.timedelta(days=day.weekday())
        label = week_start.isoformat()
        weekly_buckets[label] = _trend_bucket_template(label)

    for item in queryset:
        local_dt = timezone.localtime(item.measured_at)
        day_label = local_dt.date().isoformat()
        week_start = (local_dt.date() - timezone.timedelta(days=local_dt.date().weekday())).isoformat()

        for bucket_map, key in [(daily_buckets, day_label), (weekly_buckets, week_start)]:
            if key not in bucket_map:
                continue
            bucket = bucket_map[key]
            bucket['measurement_count'] += 1
            if getattr(item.analysis_result, 'risk_level', '') in {AlertEvent.LEVEL_HIGH, AlertEvent.LEVEL_CRITICAL}:
                bucket['high_risk_count'] += 1
            if item.heart_rate is not None:
                bucket['heart_rate_values'].append(float(item.heart_rate))
            if item.oxygen is not None:
                bucket['oxygen_values'].append(float(item.oxygen))

    alert_day_counts = defaultdict(int)
    alert_week_counts = defaultdict(int)
    for alert in alerts:
        local_dt = timezone.localtime(alert.created_at)
        alert_day_counts[local_dt.date().isoformat()] += 1
        alert_week_counts[(local_dt.date() - timezone.timedelta(days=local_dt.date().weekday())).isoformat()] += 1

    for label, count in alert_day_counts.items():
        if label in daily_buckets:
            daily_buckets[label]['alert_count'] = count
    for label, count in alert_week_counts.items():
        if label in weekly_buckets:
            weekly_buckets[label]['alert_count'] = count

    return {
        'daily': [_finalize_trend_bucket(bucket) for _, bucket in sorted(daily_buckets.items())],
        'weekly': [_finalize_trend_bucket(bucket) for _, bucket in sorted(weekly_buckets.items())],
    }


def _risk_rank(level: str | None) -> int:
    order = {
        AlertEvent.LEVEL_LOW: 1,
        AlertEvent.LEVEL_MODERATE: 2,
        AlertEvent.LEVEL_HIGH: 3,
        AlertEvent.LEVEL_CRITICAL: 4,
    }
    return order.get(level or '', 0)


def _safe_avg(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def build_home_summary(user) -> dict[str, Any]:
    latest_measurement = measurements_queryset_for_scope(user).first()
    unread_alerts = alerts_queryset_for_scope(user).filter(status=AlertEvent.STATUS_UNREAD)
    current_device = devices_queryset_for_scope(user).first()
    trends = build_measurement_trends(user)

    current_device_payload = None
    if current_device:
        current_device_payload = get_device_status_payload(current_device, user)

    return {
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role,
        },
        'counts': {
            'devices': devices_queryset_for_scope(user).count(),
            'measurements': measurements_queryset_for_scope(user).count(),
            'alerts': alerts_queryset_for_scope(user).count(),
            'unread_alerts': unread_alerts.count(),
        },
        'current_device': current_device_payload,
        'latest_measurement': None
        if latest_measurement is None
        else {
            'id': latest_measurement.id,
            'device_id': latest_measurement.device.device_id,
            'measured_at': latest_measurement.measured_at,
            'packet_kind': latest_measurement.packet_kind,
            'parsed': latest_measurement.parsed,
            'analysis': None
            if not hasattr(latest_measurement, 'analysis_result')
            else {
                'risk_level': latest_measurement.analysis_result.risk_level,
                'risk_score': float(latest_measurement.analysis_result.risk_score),
                'summary': latest_measurement.analysis_result.summary,
                'triggers': trigger_labels(latest_measurement.analysis_result.triggers),
                'trigger_codes': latest_measurement.analysis_result.triggers,
            },
        },
        'latest_alert': None
        if not unread_alerts.exists()
        else {
            'id': unread_alerts.first().id,
            'level': unread_alerts.first().level,
            'title': unread_alerts.first().title,
            'message': unread_alerts.first().message,
            'created_at': unread_alerts.first().created_at,
        },
        'trend_preview': trends['daily'],
    }


def build_measurement_chart(scope_user, metric: str, range_key: str = '7d') -> dict[str, Any]:
    metric_field_map = {
        'heart_rate': 'heart_rate',
        'oxygen': 'oxygen',
        'temperature': 'temperature',
    }
    if metric not in metric_field_map:
        raise ValueError('不支持的图表指标。')
    days_map = {'7d': 7, '30d': 30}
    days = days_map.get(range_key)
    if not days:
        raise ValueError('不支持的时间范围。')

    field_name = metric_field_map[metric]
    queryset = (
        measurements_queryset_for_scope(scope_user)
        .filter(measured_at__gte=timezone.now() - timezone.timedelta(days=days))
        .exclude(**{f'{field_name}__isnull': True})
        .order_by('measured_at')
    )

    points = []
    values: list[float] = []
    for item in queryset:
        raw_value = getattr(item, field_name)
        numeric = float(raw_value)
        values.append(numeric)
        points.append(
            {
                'measurement_id': item.id,
                'measured_at': item.measured_at,
                'value': numeric,
                'device_id': item.device.device_id,
            }
        )

    return {
        'metric': metric,
        'range': range_key,
        'points': points,
        'summary': {
            'count': len(points),
            'avg': _safe_avg(values),
            'min': min(values) if values else None,
            'max': max(values) if values else None,
        },
    }


def build_analysis_latest(scope_user) -> dict[str, Any] | None:
    latest = (
        measurements_queryset_for_scope(scope_user)
        .select_related('analysis_result', 'device', 'user')
        .filter(analysis_result__isnull=False)
        .first()
    )
    if latest is None or not hasattr(latest, 'analysis_result'):
        return None
    result = latest.analysis_result
    return {
        'measurement_id': latest.id,
        'device_id': latest.device.device_id,
        'measured_at': latest.measured_at,
        'username': latest.user.username if latest.user else '',
        'parsed': latest.parsed,
        'analysis': {
            'algorithm_version': result.algorithm_version,
            'risk_level': result.risk_level,
            'risk_score': float(result.risk_score),
            'labels': result.labels,
            'triggers': trigger_labels(result.triggers),
            'trigger_codes': result.triggers,
            'details': result.details,
            'summary': result.summary,
            'should_alert': result.should_alert,
        },
    }


def build_analysis_history(scope_user, limit: int = 20) -> list[dict[str, Any]]:
    queryset = (
        measurements_queryset_for_scope(scope_user)
        .select_related('analysis_result', 'device', 'user')
        .filter(analysis_result__isnull=False)[:limit]
    )
    items = []
    for measurement in queryset:
        result = measurement.analysis_result
        items.append(
            {
                'measurement_id': measurement.id,
                'device_id': measurement.device.device_id,
                'measured_at': measurement.measured_at,
                'packet_kind': measurement.packet_kind,
                'risk_level': result.risk_level,
                'risk_score': float(result.risk_score),
                'summary': result.summary,
                'triggers': trigger_labels(result.triggers),
                'trigger_codes': result.triggers,
            }
        )
    return items


def build_period_report(scope_user, days: int) -> dict[str, Any]:
    start_at = timezone.now() - timezone.timedelta(days=days)
    measurements = list(
        measurements_queryset_for_scope(scope_user)
        .select_related('analysis_result')
        .filter(measured_at__gte=start_at)
    )
    alerts = list(alerts_queryset_for_scope(scope_user).filter(created_at__gte=start_at))

    heart_rates = [float(item.heart_rate) for item in measurements if item.heart_rate is not None]
    oxygen_values = [float(item.oxygen) for item in measurements if item.oxygen is not None]
    risk_levels = [item.analysis_result.risk_level for item in measurements if hasattr(item, 'analysis_result')]
    trigger_counter = Counter()
    for item in measurements:
        if hasattr(item, 'analysis_result'):
            trigger_counter.update(item.analysis_result.triggers)

    peak_risk = 'low'
    for level in risk_levels:
        if _risk_rank(level) > _risk_rank(peak_risk):
            peak_risk = level

    return {
        'period_days': days,
        'start_at': start_at,
        'end_at': timezone.now(),
        'measurement_count': len(measurements),
        'alert_count': len(alerts),
        'peak_risk_level': peak_risk,
        'avg_heart_rate': _safe_avg(heart_rates),
        'avg_oxygen': _safe_avg(oxygen_values),
        'top_triggers': [
            {'code': code, 'label': trigger_label(code), 'count': count}
            for code, count in trigger_counter.most_common(5)
        ],
        'summary': (
            f'最近 {days} 天共记录 {len(measurements)} 条测量，'
            f'产生 {len(alerts)} 条告警，最高风险等级为 {peak_risk}。'
        ),
    }
