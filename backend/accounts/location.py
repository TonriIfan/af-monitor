from __future__ import annotations

import ipaddress
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


IPAPI_BASE_URL = os.getenv('IPAPI_BASE_URL', 'https://ipapi.co').rstrip('/')
IPAPI_TIMEOUT = float(os.getenv('IPAPI_TIMEOUT', '3'))
IPAPI_USER_AGENT = os.getenv('IPAPI_USER_AGENT', 'yf-monitor-dashboard/1.0')


def _blank_location() -> dict[str, Any]:
    return {
        'country': '',
        'region': '',
        'city': '',
        'latitude': None,
        'longitude': None,
        'label': '',
        'resolved': False,
    }


def build_login_location_payload(user) -> dict[str, Any]:
    parts = [user.last_login_country, user.last_login_region, user.last_login_city]
    label = ' / '.join(part for part in parts if part)
    return {
        'country': user.last_login_country,
        'region': user.last_login_region,
        'city': user.last_login_city,
        'latitude': user.last_login_latitude,
        'longitude': user.last_login_longitude,
        'label': label,
        'resolved': bool(user.last_login_latitude is not None and user.last_login_longitude is not None),
    }


def _label_from_parts(country: str, region: str, city: str) -> str:
    return ' / '.join(part for part in [country, region, city] if part)


def _is_public_ip(ip: str | None) -> bool:
    if not ip:
        return False
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not any(
        [
            parsed.is_private,
            parsed.is_loopback,
            parsed.is_link_local,
            parsed.is_reserved,
            parsed.is_multicast,
            parsed.is_unspecified,
        ]
    )


def resolve_ip_location(ip: str | None) -> dict[str, Any]:
    if not _is_public_ip(ip):
        return _blank_location()

    request = Request(
        f'{IPAPI_BASE_URL}/{ip}/json/',
        headers={
            'Accept': 'application/json',
            'User-Agent': IPAPI_USER_AGENT,
        },
    )

    try:
        with urlopen(request, timeout=IPAPI_TIMEOUT) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return _blank_location()

    if payload.get('error') or payload.get('bogon'):
        return _blank_location()

    latitude = payload.get('latitude')
    longitude = payload.get('longitude')
    if latitude is None or longitude is None:
        return _blank_location()

    country = (payload.get('country_name') or '').strip()
    region = (payload.get('region') or '').strip()
    city = (payload.get('city') or '').strip()
    return {
        'country': country,
        'region': region,
        'city': city,
        'latitude': float(latitude),
        'longitude': float(longitude),
        'label': _label_from_parts(country, region, city),
        'resolved': True,
    }


def location_from_login_context(login_context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not login_context:
        return None

    country = (login_context.get('country_name') or login_context.get('country') or '').strip()
    region = (login_context.get('region') or '').strip()
    city = (login_context.get('city') or '').strip()
    latitude = login_context.get('latitude')
    longitude = login_context.get('longitude')

    try:
        latitude = float(latitude) if latitude is not None else None
        longitude = float(longitude) if longitude is not None else None
    except (TypeError, ValueError):
        latitude = None
        longitude = None

    return {
        'country': country,
        'region': region,
        'city': city,
        'latitude': latitude,
        'longitude': longitude,
        'label': _label_from_parts(country, region, city),
        'resolved': latitude is not None and longitude is not None,
    }


def apply_login_location(user, ip: str | None, login_context: dict[str, Any] | None = None) -> dict[str, Any]:
    login_context = login_context or {}
    context_ip = (login_context.get('ip') or '').strip() or None
    final_ip = context_ip or ip
    location = location_from_login_context(login_context)
    if not location or not location['resolved']:
        location = resolve_ip_location(final_ip)

    user.last_login_ip = final_ip
    user.last_login_country = location['country']
    user.last_login_region = location['region']
    user.last_login_city = location['city']
    user.last_login_latitude = location['latitude']
    user.last_login_longitude = location['longitude']
    user.save(
        update_fields=[
            'last_login_ip',
            'last_login_country',
            'last_login_region',
            'last_login_city',
            'last_login_latitude',
            'last_login_longitude',
        ]
    )
    return build_login_location_payload(user)
