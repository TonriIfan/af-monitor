from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import AiSettings

LLM_API_BASE_URL = os.getenv('LLM_API_BASE_URL', '').strip().rstrip('/')
LLM_API_KEY = os.getenv('LLM_API_KEY', '').strip()
LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4o-mini').strip()
LLM_TIMEOUT = float(os.getenv('LLM_TIMEOUT', '8'))


def get_ai_settings() -> AiSettings:
    settings_obj, _ = AiSettings.objects.get_or_create(singleton_key='default')
    return settings_obj


def build_measurement_llm_context(measurement, analysis_result) -> dict[str, Any]:
    return {
        'measurement_id': measurement.id,
        'device_id': measurement.device.device_id,
        'username': measurement.user.username if measurement.user else '',
        'measured_at': measurement.measured_at.isoformat(),
        'packet_kind': measurement.packet_kind,
        'parsed': measurement.parsed,
        'analysis': {
            'algorithm_version': analysis_result.algorithm_version,
            'risk_level': analysis_result.risk_level,
            'risk_score': float(analysis_result.risk_score),
            'labels': analysis_result.labels,
            'triggers': analysis_result.triggers,
            'details': analysis_result.details,
            'summary': analysis_result.summary,
        },
    }


def build_demo_llm_context() -> dict[str, Any]:
    return {
        'measurement_id': 0,
        'device_id': 'demo-ring-001',
        'username': 'demo-user',
        'measured_at': '2026-03-16T09:30:00+08:00',
        'packet_kind': 'heart_rate',
        'parsed': {
            'heartRate': 118,
            'hrv': 42,
            'stress': 85,
            'oxygen': 93,
            'temperature': 37.1,
        },
        'analysis': {
            'algorithm_version': 'rules-window-baseline-v2',
            'risk_level': 'high',
            'risk_score': 0.72,
            'labels': ['较高异常心律风险', '存在连续时间窗异常', '存在个人基线偏移'],
            'triggers': [
                'realtime_tachycardia',
                'realtime_hrv_instability',
                'realtime_low_oxygen',
                'window_repeated_tachycardia_30m',
                'baseline_heart_rate_above_personal_baseline',
            ],
            'details': {
                'realtime_flags': [
                    'realtime_tachycardia',
                    'realtime_hrv_instability',
                    'realtime_low_oxygen',
                ],
                'window_flags': ['window_repeated_tachycardia_30m'],
                'baseline_flags': ['baseline_heart_rate_above_personal_baseline'],
                'window_stats': {
                    'tachycardia_count_30m': 3,
                    'low_oxygen_count_30m': 2,
                    'hrv_instability_count_30m': 3,
                    'high_risk_count_24h': 2,
                },
                'baselines': {
                    'heart_rate': 82.4,
                    'hrv': 27.6,
                    'oxygen': 97.2,
                    'temperature': 36.5,
                },
                'wearing_effective': True,
            },
            'summary': '实时异常: realtime_tachycardia, realtime_hrv_instability, realtime_low_oxygen；时间窗异常: window_repeated_tachycardia_30m；基线偏移: baseline_heart_rate_above_personal_baseline',
        },
    }


def build_llm_prompt(context: dict[str, Any]) -> str:
    return (
        '你是房颤监测系统的健康分析助手。'
        '请基于给定的测量数据与规则分析结果，输出简明、谨慎、不夸大诊断结论的中文说明。'
        '你只能给出风险解读与就医建议方向，不能给出医学确诊。'
        '请返回三部分：1. 结果解读 2. 触发原因 3. 建议动作。'
        f'\n\n上下文数据：\n{json.dumps(context, ensure_ascii=False, indent=2)}'
    )


def build_ai_chat_prompt(context: dict[str, Any], user_message: str) -> str:
    return (
        '你是房颤监测系统中的健康解读助手。'
        '请结合用户的近期监测概况、风险趋势、告警记录和当前提问，'
        '用简洁、谨慎、面向患者的中文给出解读与建议。'
        '不能做临床确诊，不能夸大风险。'
        f'\n\n用户问题：{user_message}'
        f'\n\n上下文数据：\n{json.dumps(context, ensure_ascii=False, indent=2)}'
    )


def build_patient_friendly_template(context: dict[str, Any]) -> str:
    analysis = context['analysis']
    details = analysis.get('details') or {}
    realtime_flags = details.get('realtime_flags') or []
    window_flags = details.get('window_flags') or []
    baseline_flags = details.get('baseline_flags') or []

    title = f"风险等级：{analysis['risk_level']}（分数 {analysis['risk_score']:.2f}）"
    interpretation = analysis.get('summary') or '本次未发现明显异常。'
    causes = []
    if realtime_flags:
        causes.append(f"本次测量即时异常：{', '.join(realtime_flags)}")
    if window_flags:
        causes.append(f"最近时间窗异常：{', '.join(window_flags)}")
    if baseline_flags:
        causes.append(f"与个人历史基线相比的偏移：{', '.join(baseline_flags)}")
    if not causes:
        causes.append('当前没有检测到明确的连续异常特征。')

    advice = [
        '请继续保持佩戴并观察后续趋势，不要仅凭单次结果做医学判断。',
        '如果连续多次出现高风险提示，或伴随胸闷、心悸、头晕等不适，应尽快就医。',
    ]
    if analysis['risk_level'] in {'high', 'critical'}:
        advice.insert(0, '建议尽快复测并关注最近 30 分钟内是否持续异常。')

    return '\n'.join(
        [
            '1. 结果解读',
            title,
            interpretation,
            '',
            '2. 触发原因',
            *causes,
            '',
            '3. 建议动作',
            *advice,
        ]
    )


def build_patient_chat_template(context: dict[str, Any], user_message: str) -> str:
    latest = context.get('latest_analysis') or {}
    latest_level = latest.get('risk_level') or 'unknown'
    latest_summary = latest.get('summary') or '近期暂无明显异常结论。'
    unread_alerts = context.get('unread_alert_count', 0)
    return '\n'.join(
        [
            f'针对你的问题“{user_message}”，系统先给出辅助说明：',
            f'1. 最近一次风险等级为 {latest_level}。',
            f'2. 最近一次分析摘要：{latest_summary}',
            f'3. 当前未读告警数：{unread_alerts}。',
            '4. 这类结果适合用于风险提醒和持续观察，不能替代心电图或医生面诊。',
            '5. 如果近期连续出现高风险提示，或伴随心悸、胸闷、头晕、乏力，应尽快就医。',
        ]
    )


def _effective_settings(settings_obj: AiSettings, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    return {
        'enabled': overrides.get('enabled', settings_obj.enabled),
        'mode': overrides.get('mode', settings_obj.mode),
        'api_base_url': overrides.get('api_base_url', settings_obj.api_base_url) or LLM_API_BASE_URL,
        'api_key': overrides.get('api_key', settings_obj.api_key) or LLM_API_KEY,
        'model': overrides.get('model', settings_obj.model) or LLM_MODEL,
        'temperature': float(overrides.get('temperature', settings_obj.temperature)),
        'system_prompt': overrides.get('system_prompt', settings_obj.system_prompt),
    }


def request_llm_insight(context: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    settings_obj = get_ai_settings()
    effective = _effective_settings(settings_obj, overrides)
    prompt = build_llm_prompt(context)
    template_content = build_patient_friendly_template(context)
    payload = {
        'available': bool(effective['enabled']),
        'mode': effective['mode'],
        'provider': effective['mode'],
        'model': effective['model'],
        'prompt': prompt,
        'context': context,
        'content': template_content,
        'template_content': template_content,
        'source': 'template',
    }

    if not effective['enabled'] or effective['mode'] in {AiSettings.MODE_DISABLED, AiSettings.MODE_TEMPLATE}:
        return payload

    api_base_url = effective['api_base_url']
    api_key = effective['api_key']
    model = effective['model']

    if effective['mode'] != AiSettings.MODE_OPENAI_COMPATIBLE or not api_base_url or not api_key:
        payload['source'] = 'template_fallback'
        return payload

    request_body = json.dumps(
        {
            'model': model,
            'messages': [
                {'role': 'system', 'content': effective['system_prompt'] or '你是谨慎的健康监测辅助分析助手。'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': effective['temperature'],
        }
    ).encode('utf-8')

    request = Request(
        f'{api_base_url}/chat/completions',
        data=request_body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=LLM_TIMEOUT) as response:
            response_payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        payload['error'] = str(exc)
        payload['source'] = 'template_fallback'
        return payload

    content = (
        response_payload.get('choices', [{}])[0]
        .get('message', {})
        .get('content', '')
        .strip()
    )
    payload['available'] = True
    payload['content'] = content
    payload['source'] = 'llm'
    return payload


def request_ai_chat(context: dict[str, Any], user_message: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    settings_obj = get_ai_settings()
    effective = _effective_settings(settings_obj, overrides)
    prompt = build_ai_chat_prompt(context, user_message)
    template_content = build_patient_chat_template(context, user_message)
    payload = {
        'available': bool(effective['enabled']),
        'mode': effective['mode'],
        'provider': effective['mode'],
        'model': effective['model'],
        'prompt': prompt,
        'context': context,
        'content': template_content,
        'source': 'template',
    }

    if not effective['enabled'] or effective['mode'] in {AiSettings.MODE_DISABLED, AiSettings.MODE_TEMPLATE}:
        return payload

    api_base_url = effective['api_base_url']
    api_key = effective['api_key']
    model = effective['model']

    if effective['mode'] != AiSettings.MODE_OPENAI_COMPATIBLE or not api_base_url or not api_key:
        payload['source'] = 'template_fallback'
        return payload

    request_body = json.dumps(
        {
            'model': model,
            'messages': [
                {'role': 'system', 'content': effective['system_prompt'] or '你是谨慎的健康监测辅助分析助手。'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': effective['temperature'],
        }
    ).encode('utf-8')

    request = Request(
        f'{api_base_url}/chat/completions',
        data=request_body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=LLM_TIMEOUT) as response:
            response_payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        payload['error'] = str(exc)
        payload['source'] = 'template_fallback'
        return payload

    content = (
        response_payload.get('choices', [{}])[0]
        .get('message', {})
        .get('content', '')
        .strip()
    )
    payload['available'] = True
    payload['content'] = content
    payload['source'] = 'llm'
    return payload
