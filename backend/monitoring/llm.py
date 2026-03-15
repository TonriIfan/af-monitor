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
            'summary': analysis_result.summary,
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


def request_llm_insight(context: dict[str, Any]) -> dict[str, Any]:
    settings_obj = get_ai_settings()
    prompt = build_llm_prompt(context)
    template_content = build_patient_friendly_template(context)
    payload = {
        'available': settings_obj.enabled,
        'mode': settings_obj.mode,
        'provider': settings_obj.mode,
        'model': settings_obj.model,
        'prompt': prompt,
        'context': context,
        'content': template_content,
        'template_content': template_content,
        'source': 'template',
    }

    if not settings_obj.enabled or settings_obj.mode in {AiSettings.MODE_DISABLED, AiSettings.MODE_TEMPLATE}:
        return payload

    api_base_url = settings_obj.api_base_url or LLM_API_BASE_URL
    api_key = settings_obj.api_key or LLM_API_KEY
    model = settings_obj.model or LLM_MODEL

    if settings_obj.mode != AiSettings.MODE_OPENAI_COMPATIBLE or not api_base_url or not api_key:
        payload['source'] = 'template_fallback'
        return payload

    request_body = json.dumps(
        {
            'model': model,
            'messages': [
                {'role': 'system', 'content': settings_obj.system_prompt or '你是谨慎的健康监测辅助分析助手。'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': float(settings_obj.temperature),
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
