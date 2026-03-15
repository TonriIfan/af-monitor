from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from devices.models import Device, DeviceBinding
from monitoring.services import ingest_packet


User = get_user_model()


@dataclass(frozen=True)
class HeartRateSample:
    heart_rate: int
    hrv: int
    stress: int
    temperature: float


@dataclass(frozen=True)
class OxygenSample:
    wear_status: int
    heart_rate: int
    oxygen: int
    temperature: float


def _to_temp_bytes(value: float) -> list[int]:
    raw = int(round(value * 100))
    return list(raw.to_bytes(2, byteorder='little', signed=False))


def build_heart_rate_frame(sample: HeartRateSample) -> str:
    frame = [
        0x00,
        0x00,
        0x31,
        0x00,
        0x03,
        sample.heart_rate,
        sample.hrv,
        sample.stress,
        *_to_temp_bytes(sample.temperature),
    ]
    return ' '.join(f'{value:02X}' for value in frame)


def build_oxygen_frame(sample: OxygenSample) -> str:
    frame = [
        0x00,
        0x00,
        0x32,
        0x00,
        sample.wear_status,
        sample.heart_rate,
        sample.oxygen,
        *_to_temp_bytes(sample.temperature),
    ]
    return ' '.join(f'{value:02X}' for value in frame)


def normal_samples() -> tuple[list[HeartRateSample], list[OxygenSample]]:
    return (
        [
            HeartRateSample(74, 18, 26, 36.52),
            HeartRateSample(78, 21, 34, 36.61),
            HeartRateSample(72, 19, 28, 36.47),
            HeartRateSample(80, 23, 36, 36.58),
        ],
        [
            OxygenSample(0x03, 75, 98, 36.42),
            OxygenSample(0x03, 79, 97, 36.40),
        ],
    )


def high_risk_samples() -> tuple[list[HeartRateSample], list[OxygenSample]]:
    return (
        [
            HeartRateSample(116, 37, 82, 37.10),
            HeartRateSample(121, 42, 88, 37.24),
            HeartRateSample(124, 40, 91, 37.35),
            HeartRateSample(118, 39, 85, 37.18),
        ],
        [
            OxygenSample(0x03, 119, 93, 36.98),
            OxygenSample(0x03, 123, 92, 37.02),
        ],
    )


def baseline_spike_samples(index: int, count: int) -> tuple[HeartRateSample, OxygenSample | None]:
    spike_start = max(1, int(count * 0.7))
    if index < spike_start:
        return HeartRateSample(76 + (index % 4), 20 + (index % 3), 30 + (index % 8), 36.55 + ((index % 3) * 0.03)), None
    return (
        HeartRateSample(118 + (index % 5), 38 + (index % 4), 82 + (index % 10), 37.12 + ((index % 3) * 0.04)),
        OxygenSample(0x03, 116 + (index % 4), 92 + (index % 2), 36.94 + ((index % 2) * 0.03)),
    )


def trend_samples(index: int) -> tuple[HeartRateSample, OxygenSample]:
    if index % 6 in {0, 1}:
        return (
            HeartRateSample(118 + (index % 4), 36 + (index % 3), 82 + (index % 6), 37.08 + ((index % 2) * 0.05)),
            OxygenSample(0x03, 116 + (index % 3), 92 + (index % 2), 36.95),
        )
    return (
        HeartRateSample(73 + (index % 5), 18 + (index % 4), 25 + (index % 10), 36.48 + ((index % 3) * 0.04)),
        OxygenSample(0x03, 75 + (index % 4), 97 + (index % 2), 36.41),
    )


class Command(BaseCommand):
    help = 'Generate mock monitoring packets to test analysis, trends, and alerts.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='mock-user')
        parser.add_argument('--password', default='mock12345')
        parser.add_argument('--device-id', default='mock-ring-001')
        parser.add_argument(
            '--scenario',
            choices=['normal', 'high_risk', 'baseline_spike', 'trend'],
            default='baseline_spike',
        )
        parser.add_argument('--count', type=int, default=24)
        parser.add_argument('--interval-minutes', type=int, default=15)
        parser.add_argument('--start-at', default='')
        parser.add_argument('--source', default='mock-generator')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        device_id = options['device_id']
        scenario = options['scenario']
        count = options['count']
        interval_minutes = options['interval_minutes']
        start_at = options['start_at']
        source = options['source']

        if count <= 0:
            raise CommandError('--count 必须大于 0。')
        if interval_minutes <= 0:
            raise CommandError('--interval-minutes 必须大于 0。')

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'role': User.Role.USER,
                'is_active': True,
                'email': f'{username}@demo.local',
            },
        )
        if created:
            user.set_password(password)
            user.save()

        device, _ = Device.objects.get_or_create(
            device_id=device_id,
            defaults={
                'name': device_id,
                'source': source,
            },
        )
        DeviceBinding.objects.get_or_create(user=user, device=device, defaults={'is_active': True})

        start_dt = self._resolve_start_time(start_at, count, interval_minutes)
        created_packets = 0

        for index, packet in enumerate(self._build_packets(scenario, count, start_dt, interval_minutes, device_id, source)):
            ingest_packet(packet, raw_payload=packet, request_user=user)
            created_packets += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Mock monitoring data generated: user={username}, device={device_id}, scenario={scenario}, packets={created_packets}'
            )
        )

    def _resolve_start_time(self, start_at: str, count: int, interval_minutes: int):
        if start_at:
            parsed = parse_datetime(start_at)
            if parsed is None:
                raise CommandError('--start-at 必须是 ISO 8601 时间，例如 2026-03-16T08:00:00+08:00')
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed
        return timezone.now() - timedelta(minutes=(count - 1) * interval_minutes)

    def _build_packets(
        self,
        scenario: str,
        count: int,
        start_dt,
        interval_minutes: int,
        device_id: str,
        source: str,
    ) -> Iterable[dict]:
        normal_hr, normal_ox = normal_samples()
        risk_hr, risk_ox = high_risk_samples()

        for index in range(count):
            measured_at = start_dt + timedelta(minutes=index * interval_minutes)

            if scenario == 'normal':
                hr_sample = normal_hr[index % len(normal_hr)]
                ox_sample = normal_ox[index % len(normal_ox)] if index % 4 == 0 else None
            elif scenario == 'high_risk':
                hr_sample = risk_hr[index % len(risk_hr)]
                ox_sample = risk_ox[index % len(risk_ox)] if index % 2 == 0 else None
            elif scenario == 'trend':
                hr_sample, ox_sample = trend_samples(index)
            else:
                hr_sample, ox_sample = baseline_spike_samples(index, count)

            yield {
                'device_id': device_id,
                'client_time': measured_at.isoformat(),
                'source': source,
                'payload': {
                    'frame_hex': build_heart_rate_frame(hr_sample),
                },
            }

            if ox_sample is not None:
                yield {
                    'device_id': device_id,
                    'client_time': (measured_at + timedelta(seconds=30)).isoformat(),
                    'source': source,
                    'payload': {
                        'frame_hex': build_oxygen_frame(ox_sample),
                    },
                }
