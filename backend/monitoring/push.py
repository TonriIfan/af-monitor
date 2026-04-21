from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings


@dataclass
class PushSendResult:
    success: bool
    message_id: str = ''
    error_code: str = ''
    error_message: str = ''
    retryable: bool = False
    invalid_token: bool = False


def _coerce_error_code(exc: Exception) -> str:
    candidates = [
        getattr(exc, 'code', ''),
        getattr(exc, 'detail', ''),
        exc.__class__.__name__,
    ]
    for item in candidates:
        if item:
            return str(item)
    return 'unknown_error'


def _is_retryable_error(exc: Exception) -> bool:
    error_text = f'{exc.__class__.__name__} {exc}'.lower()
    return any(
        token in error_text
        for token in ['quota', 'timeout', 'tempor', 'unavailable', 'internal', '503', '500']
    )


def _is_invalid_token_error(exc: Exception) -> bool:
    error_text = f'{exc.__class__.__name__} {exc}'.lower()
    return any(
        token in error_text
        for token in ['unregistered', 'registration-token-not-registered', 'invalid-registration-token', 'senderid']
    )


def _get_firebase_app():
    import firebase_admin
    from firebase_admin import credentials

    try:
        return firebase_admin.get_app()
    except ValueError:
        options: dict[str, Any] = {}
        if settings.FCM_PROJECT_ID:
            options['projectId'] = settings.FCM_PROJECT_ID
        if settings.FCM_CREDENTIALS_JSON:
            cert = credentials.Certificate(json.loads(settings.FCM_CREDENTIALS_JSON))
            return firebase_admin.initialize_app(cert, options or None)
        if settings.FCM_CREDENTIALS_FILE:
            cert = credentials.Certificate(settings.FCM_CREDENTIALS_FILE)
            return firebase_admin.initialize_app(cert, options or None)
        return firebase_admin.initialize_app(options=options or None)


class FcmPushProvider:
    provider_name = 'fcm'

    def send_alert(self, delivery, payload: dict[str, Any]) -> PushSendResult:
        if not settings.FCM_ENABLED:
            return PushSendResult(
                success=False,
                error_code='fcm_disabled',
                error_message='FCM 未启用。',
                retryable=False,
            )

        try:
            _get_firebase_app()
            from firebase_admin import messaging
        except ImportError as exc:
            return PushSendResult(
                success=False,
                error_code='firebase_admin_missing',
                error_message=str(exc),
                retryable=False,
            )
        except Exception as exc:
            return PushSendResult(
                success=False,
                error_code='fcm_config_error',
                error_message=str(exc),
                retryable=False,
            )

        ttl = timedelta(seconds=max(int(settings.FCM_TTL_SECONDS or 0), 0))
        message = messaging.Message(
            token=delivery.device_token,
            notification=messaging.Notification(
                title=payload['notification']['title'],
                body=payload['notification']['body'],
            ),
            data=payload['data'],
            android=messaging.AndroidConfig(
                priority='high',
                ttl=ttl,
                notification=messaging.AndroidNotification(sound='default'),
            ),
            apns=messaging.APNSConfig(
                headers={
                    'apns-priority': '10',
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        content_available=True,
                    )
                ),
            ),
        )
        try:
            message_id = messaging.send(message)
        except Exception as exc:
            return PushSendResult(
                success=False,
                error_code=_coerce_error_code(exc),
                error_message=str(exc),
                retryable=_is_retryable_error(exc),
                invalid_token=_is_invalid_token_error(exc),
            )

        return PushSendResult(success=True, message_id=str(message_id))


def get_push_provider(provider_name: str):
    if provider_name == 'fcm':
        return FcmPushProvider()
    raise ValueError(f'不支持的推送 provider: {provider_name}')
