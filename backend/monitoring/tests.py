import csv
import importlib.util
import json
import pickle
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from devices.models import Device, DeviceBinding
from monitoring.management.commands import prepare_cpsc2021_rr_af_csv as cpsc_command

from .ml import analyze_structured_measurement_window
from .models import (
    AiSettings,
    AlertEvent,
    Measurement,
    PpgAnalysisRecord,
    PushDeviceRegistration,
    RawPacket,
    SymptomFeedback,
)
from .services import parse_packet


def build_ppg_window(
    irregular: bool = False, sample_rate_hz: int = 25, seconds: int = 12
) -> list[float]:
    import math

    total = sample_rate_hz * seconds
    samples: list[float] = []
    for index in range(total):
        t = index / sample_rate_hz
        base = math.sin(2 * math.pi * 1.2 * t) + 0.15 * math.sin(2 * math.pi * 2.4 * t)
        modulation = 0.0
        if irregular:
            modulation = 0.35 * math.sin(2 * math.pi * 0.22 * t) + 0.20 * math.sin(
                2 * math.pi * 0.41 * t
            )
        samples.append(base + modulation)
    return samples


def workspace_temp_path(filename: str) -> Path:
    base_dir = Path(__file__).resolve().parent.parent / ".tmp-tests"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / filename


def build_heart_rate_frame_hex(
    heart_rate: int, hrv: int = 24, stress: int = 32, temperature_raw: int = 3694
) -> str:
    temp_low = temperature_raw & 0xFF
    temp_high = (temperature_raw >> 8) & 0xFF
    return f"00 00 31 00 03 {heart_rate:02X} {hrv:02X} {stress:02X} {temp_low:02X} {temp_high:02X}"


class DummyStructuredAfEstimator:
    def predict_proba(self, rows):
        return [[0.08, 0.92] for _ in rows]


class PacketParserTests(APITestCase):
    def test_parse_heart_rate_packet(self):
        result = parse_packet(
            {
                "frame_hex": "00 00 31 00 03 48 24 50 8E 0E",
            }
        )

        self.assertEqual(result.packet_kind, "heart_rate")
        self.assertEqual(result.parsed["heartRate"], 72)
        self.assertEqual(result.parsed["hrv"], 36)
        self.assertEqual(result.parsed["stress"], 80)
        self.assertAlmostEqual(result.parsed["temperature"], 37.26, places=2)

    def test_generate_mock_monitoring_data_command_creates_measurements(self):
        call_command(
            "generate_mock_monitoring_data",
            username="cmd-user",
            device_id="cmd-ring-001",
            scenario="trend",
            count=4,
            interval_minutes=30,
        )

        self.assertTrue(get_user_model().objects.filter(username="cmd-user").exists())
        self.assertTrue(Device.objects.filter(device_id="cmd-ring-001").exists())
        self.assertGreater(
            Measurement.objects.filter(device__device_id="cmd-ring-001").count(), 0
        )


class PacketIngestApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="monitor-user",
            password="pass12345",
        )
        self.device = Device.objects.create(
            device_id="ring-001", source="wechat-miniapp"
        )
        DeviceBinding.objects.create(user=self.user, device=self.device)
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_packet_ingest_accepts_web_bluetooth_source(self):
        """Webapp via Web Bluetooth uploads packets with source='web-bluetooth' while authenticated."""
        response = self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T14:25:00+08:00",
                "source": "web-bluetooth",
                "payload": {
                    "frame_hex": "00 00 31 00 03 5A 18 20 6E 0E",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["raw_payload"]["source"], "web-bluetooth")
        self.assertEqual(response.data["parsed"]["heartRate"], 90)
        # 登录态下的上报应归属到请求用户，而不是回落到设备绑定关系
        self.assertEqual(response.data["user_id"], self.user.id)

    def test_packet_ingest_preserves_raw_payload_and_returns_analysis(self):
        self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T14:20:00+08:00",
                "source": "wechat-miniapp",
                "payload": {
                    "frame_hex": "00 00 31 00 03 5A 18 20 6E 0E",
                },
            },
            format="json",
        )
        payload = {
            "device_id": "ring-001",
            "client_time": "2026-03-15T14:30:00+08:00",
            "source": "wechat-miniapp",
            "payload": {
                "frame_hex": "00 00 31 00 03 78 28 55 8E 0E",
                "frame_bytes": [0, 0, 49, 0, 3, 120, 40, 85, 142, 14],
            },
        }

        response = self.client.post("/api/v1/packets", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["raw_payload"]["payload"], payload["payload"])
        self.assertEqual(response.data["parsed"]["heartRate"], 120)
        self.assertTrue(response.data["analysis"]["should_alert"])
        self.assertEqual(
            response.data["analysis"]["algorithm_version"], "structured-ml-primary-v1"
        )
        self.assertIn("details", response.data["analysis"])
        self.assertIn("ml", response.data["analysis"]["details"])
        self.assertTrue(response.data["alert_state"]["has_alert"])
        self.assertGreaterEqual(RawPacket.objects.count(), 2)
        self.assertEqual(AlertEvent.objects.count(), 1)

    def test_measurement_queries_and_alert_read(self):
        self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T14:31:00+08:00",
                "source": "wechat-miniapp",
                "payload": {
                    "frame_hex": "00 00 31 00 03 78 28 55 8E 0E",
                },
            },
            format="json",
        )

        list_response = self.client.get("/api/v1/measurements?device_id=ring-001")
        latest_response = self.client.get(
            "/api/v1/measurements/latest?device_id=ring-001"
        )
        alerts_response = self.client.get("/api/v1/alerts?device_id=ring-001")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(latest_response.status_code, status.HTTP_200_OK)
        self.assertEqual(alerts_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(len(alerts_response.data), 1)

        alert_id = alerts_response.data[0]["id"]
        read_response = self.client.post(
            f"/api/v1/alerts/{alert_id}/read", {}, format="json"
        )
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertTrue(read_response.data["is_read"])

    def test_device_status_returns_latest_measurement(self):
        self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T14:31:00+08:00",
                "source": "wechat-miniapp",
                "payload": {
                    "frame_hex": "00 00 12 00 64",
                },
            },
            format="json",
        )

        response = self.client.get("/api/v1/devices/ring-001/status")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["device_id"], "ring-001")
        self.assertEqual(
            response.data["latest_measurement"]["parsed"]["batteryLevel"], 100
        )

    def test_dashboard_overview_returns_counts(self):
        self.user.last_login_ip = "1.1.1.1"
        self.user.last_login_country = "China"
        self.user.last_login_region = "Beijing"
        self.user.last_login_city = "Beijing"
        self.user.last_login_latitude = 39.9042
        self.user.last_login_longitude = 116.4074
        self.user.save(
            update_fields=[
                "last_login_ip",
                "last_login_country",
                "last_login_region",
                "last_login_city",
                "last_login_latitude",
                "last_login_longitude",
            ]
        )

        self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T14:31:00+08:00",
                "source": "wechat-miniapp",
                "payload": {
                    "frame_hex": "00 00 31 00 03 78 28 55 8E 0E",
                },
            },
            format="json",
        )

        response = self.client.get("/api/v1/dashboard/overview")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["counts"]["devices"], 1)
        self.assertEqual(response.data["counts"]["measurements"], 1)
        self.assertGreaterEqual(response.data["counts"]["alerts"], 1)
        self.assertEqual(
            response.data["user_summaries"][0]["last_login_location"]["city"], "Beijing"
        )

    def test_analysis_v2_detects_window_and_baseline_flags(self):
        for minute_value, frame_hex in [
            (0, "00 00 31 00 03 5A 10 10 60 0E"),
            (35, "00 00 31 00 03 78 28 40 70 0E"),
            (45, "00 00 31 00 03 79 29 45 72 0E"),
        ]:
            self.client.post(
                "/api/v1/packets",
                {
                    "device_id": "ring-001",
                    "client_time": f"2026-03-15T14:{minute_value:02d}:00+08:00",
                    "source": "wechat-miniapp",
                    "payload": {"frame_hex": frame_hex},
                },
                format="json",
            )

        response = self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T14:59:00+08:00",
                "source": "wechat-miniapp",
                "payload": {"frame_hex": "00 00 31 00 03 82 30 55 68 0E"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        triggers = response.data["analysis"]["triggers"]
        self.assertIn("window_repeated_tachycardia_30m", triggers)
        self.assertIn("baseline_heart_rate_above_personal_baseline", triggers)
        self.assertIn("window_stats", response.data["analysis"]["details"])
        self.assertIn("baselines", response.data["analysis"]["details"])

    def test_measurement_llm_insight_returns_prompt_when_provider_disabled(self):
        ingest = self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T15:00:00+08:00",
                "source": "wechat-miniapp",
                "payload": {"frame_hex": "00 00 31 00 03 78 28 55 8E 0E"},
            },
            format="json",
        )

        response = self.client.post(
            f"/api/v1/measurements/{ingest.data['id']}/llm-insight", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["available"])
        self.assertIn("prompt", response.data)
        self.assertIn("context", response.data)
        self.assertEqual(response.data["source"], "template")

    def test_measurement_trends_returns_daily_and_weekly_stats(self):
        for timestamp, frame_hex in [
            ("2026-03-10T10:00:00+08:00", "00 00 31 00 03 60 20 20 70 0E"),
            ("2026-03-15T10:00:00+08:00", "00 00 31 00 03 78 28 55 8E 0E"),
        ]:
            self.client.post(
                "/api/v1/packets",
                {
                    "device_id": "ring-001",
                    "client_time": timestamp,
                    "source": "wechat-miniapp",
                    "payload": {"frame_hex": frame_hex},
                },
                format="json",
            )

        response = self.client.get("/api/v1/measurements/trends")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("daily", response.data)
        self.assertIn("weekly", response.data)
        self.assertEqual(len(response.data["daily"]), 7)
        self.assertEqual(len(response.data["weekly"]), 8)

    def test_admin_can_update_ai_settings(self):
        admin = get_user_model().objects.create_user(
            username="manager",
            password="pass12345",
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")

        response = self.client.put(
            "/api/v1/ai/settings",
            {
                "enabled": True,
                "mode": "template",
                "model": "gpt-5.2",
                "system_prompt": "test prompt",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        settings_obj = AiSettings.objects.get(singleton_key="default")
        self.assertTrue(settings_obj.enabled)
        self.assertEqual(settings_obj.mode, "template")
        self.assertEqual(settings_obj.system_prompt, "test prompt")

    def test_admin_can_test_ai_settings_with_template_mode(self):
        admin = get_user_model().objects.create_user(
            username="manager-test",
            password="pass12345",
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")

        response = self.client.post(
            "/api/v1/ai/settings/test",
            {
                "enabled": True,
                "mode": "template",
                "model": "gpt-4o-mini",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        self.assertEqual(response.data["source"], "template")
        self.assertIn("结果解读", response.data["content"])

    def test_staff_can_scope_dashboard_by_user(self):
        other_user = get_user_model().objects.create_user(
            username="other-user",
            password="pass12345",
        )
        other_device = Device.objects.create(
            device_id="ring-002", source="wechat-miniapp"
        )
        DeviceBinding.objects.create(user=other_user, device=other_device)

        self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T14:31:00+08:00",
                "source": "wechat-miniapp",
                "payload": {"frame_hex": "00 00 12 00 64"},
            },
            format="json",
        )

        admin = get_user_model().objects.create_user(
            username="manager",
            password="pass12345",
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")

        self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-002",
                "client_time": "2026-03-15T14:32:00+08:00",
                "source": "wechat-miniapp",
                "payload": {"frame_hex": "00 00 12 00 32"},
            },
            format="json",
        )

        global_response = self.client.get("/api/v1/dashboard/overview")
        scoped_response = self.client.get(
            f"/api/v1/dashboard/overview?user_id={self.user.id}"
        )

        self.assertEqual(global_response.status_code, status.HTTP_200_OK)
        self.assertEqual(global_response.data["counts"]["devices"], 2)
        self.assertEqual(scoped_response.status_code, status.HTTP_200_OK)
        self.assertEqual(scoped_response.data["counts"]["devices"], 1)

    def test_admin_accounts_are_excluded_from_global_monitoring_views(self):
        admin = get_user_model().objects.create_user(
            username="manager",
            password="pass12345",
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
            last_login_ip="39.100.10.10",
            last_login_country="China",
            last_login_region="北京市",
            last_login_city="北京市",
            last_login_latitude=39.9042,
            last_login_longitude=116.4074,
        )
        admin_device = Device.objects.create(
            device_id="ring-admin", source="wechat-miniapp"
        )
        DeviceBinding.objects.create(user=admin, device=admin_device)

        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")
        self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-admin",
                "client_time": "2026-03-15T14:40:00+08:00",
                "source": "wechat-miniapp",
                "payload": {"frame_hex": "00 00 12 00 64"},
            },
            format="json",
        )

        response = self.client.get("/api/v1/dashboard/overview")
        measurements_response = self.client.get("/api/v1/measurements")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["counts"]["devices"], 1)
        self.assertEqual(len(response.data["user_summaries"]), 1)
        self.assertEqual(
            response.data["user_summaries"][0]["username"], self.user.username
        )
        self.assertEqual(measurements_response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            all(item["username"] != "manager" for item in measurements_response.data)
        )

    def test_app_home_summary_and_detail_endpoints_work(self):
        ingest = self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T16:00:00+08:00",
                "source": "wechat-miniapp",
                "payload": {"frame_hex": "00 00 31 00 03 78 28 55 8E 0E"},
            },
            format="json",
        )
        alert = AlertEvent.objects.first()

        summary_response = self.client.get("/api/v1/home/summary")
        measurement_detail_response = self.client.get(
            f"/api/v1/measurements/{ingest.data['id']}"
        )
        alert_detail_response = self.client.get(f"/api/v1/alerts/{alert.id}")

        self.assertEqual(summary_response.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_response.data["counts"]["measurements"], 1)
        self.assertEqual(measurement_detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(alert_detail_response.status_code, status.HTTP_200_OK)

    def test_alert_read_all_and_unread_count(self):
        self.client.post(
            "/api/v1/packets",
            {
                "device_id": "ring-001",
                "client_time": "2026-03-15T16:10:00+08:00",
                "source": "wechat-miniapp",
                "payload": {"frame_hex": "00 00 31 00 03 78 28 55 8E 0E"},
            },
            format="json",
        )

        unread_response = self.client.get("/api/v1/alerts/unread-count")
        read_all_response = self.client.post(
            "/api/v1/alerts/read-all", {}, format="json"
        )

        self.assertEqual(unread_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(unread_response.data["unread_count"], 1)
        self.assertEqual(read_all_response.status_code, status.HTTP_200_OK)
        self.assertEqual(AlertEvent.objects.filter(status="unread").count(), 0)

    def test_chart_analysis_and_reports_endpoints(self):
        for timestamp, frame_hex in [
            ("2026-03-10T10:00:00+08:00", "00 00 31 00 03 60 20 20 70 0E"),
            ("2026-03-15T10:00:00+08:00", "00 00 31 00 03 78 28 55 8E 0E"),
        ]:
            self.client.post(
                "/api/v1/packets",
                {
                    "device_id": "ring-001",
                    "client_time": timestamp,
                    "source": "wechat-miniapp",
                    "payload": {"frame_hex": frame_hex},
                },
                format="json",
            )

        chart_response = self.client.get(
            "/api/v1/measurements/chart?metric=heart_rate&range=7d"
        )
        latest_response = self.client.get("/api/v1/analysis/latest")
        history_response = self.client.get("/api/v1/analysis/history?limit=5")
        weekly_response = self.client.get("/api/v1/reports/weekly")
        monthly_response = self.client.get("/api/v1/reports/monthly")

        self.assertEqual(chart_response.status_code, status.HTTP_200_OK)
        self.assertIn("points", chart_response.data)
        self.assertEqual(latest_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(weekly_response.status_code, status.HTTP_200_OK)
        self.assertEqual(monthly_response.status_code, status.HTTP_200_OK)

    def test_feedback_push_batch_and_ai_chat_endpoints(self):
        batch_response = self.client.post(
            "/api/v1/measurements/batch",
            {
                "items": [
                    {
                        "device_id": "ring-001",
                        "client_time": "2026-03-15T17:00:00+08:00",
                        "source": "wechat-miniapp",
                        "payload": {"frame_hex": "00 00 31 00 03 78 28 55 8E 0E"},
                    },
                    {
                        "device_id": "ring-001",
                        "client_time": "2026-03-15T17:10:00+08:00",
                        "source": "wechat-miniapp",
                        "payload": {"frame_hex": "00 00 32 00 03 78 5D 6E 0E"},
                    },
                ]
            },
            format="json",
        )
        feedback_response = self.client.post(
            "/api/v1/feedback/symptoms",
            {
                "symptoms": ["palpitation", "dizziness"],
                "severity": 4,
                "duration_minutes": 15,
                "notes": "晚间发作",
                "occurred_at": "2026-03-15T17:30:00+08:00",
            },
            format="json",
        )
        push_response = self.client.post(
            "/api/v1/push/register-device",
            {
                "device_token": "push-token-001",
                "platform": "android",
                "app_version": "1.0.0",
                "device_name": "Pixel",
                "is_active": True,
            },
            format="json",
        )
        chat_response = self.client.post(
            "/api/v1/ai/chat", {"message": "我现在需要马上去医院吗？"}, format="json"
        )

        self.assertEqual(batch_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(batch_response.data["created_count"], 2)
        self.assertEqual(feedback_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SymptomFeedback.objects.filter(user=self.user).exists())
        self.assertEqual(push_response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            PushDeviceRegistration.objects.filter(
                user=self.user, device_token="push-token-001"
            ).exists()
        )
        self.assertEqual(chat_response.status_code, status.HTTP_200_OK)
        self.assertIn("content", chat_response.data)

    def test_ppg_analyze_endpoint_creates_record(self):
        response = self.client.post(
            "/api/v1/ml/ppg-analyze",
            {
                "device_id": "ring-001",
                "collected_at": "2026-03-15T18:00:00+08:00",
                "source": "app_upload",
                "sample_rate_hz": 25,
                "samples": build_ppg_window(irregular=True),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["device_id"], "ring-001")
        self.assertIn("af_probability", response.data)
        self.assertIn("model_version", response.data)
        self.assertTrue(
            PpgAnalysisRecord.objects.filter(
                device=self.device, user=self.user
            ).exists()
        )

    def test_ppg_analyze_rejects_short_window(self):
        response = self.client.post(
            "/api/v1/ml/ppg-analyze",
            {
                "device_id": "ring-001",
                "collected_at": "2026-03-15T18:01:00+08:00",
                "sample_rate_hz": 25,
                "samples": [0.1] * 50,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("samples", response.data)

    def test_train_ppg_af_model_command_writes_model_artifact(self):
        if importlib.util.find_spec("sklearn") is None:
            self.skipTest("当前环境未安装 scikit-learn。")

        csv_path = workspace_temp_path("ppg_windows.csv")
        model_path = workspace_temp_path("ppg_af_model.pkl")
        for path in [csv_path, model_path]:
            if path.exists():
                path.unlink()

        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "record_id",
                    "group_id",
                    "label",
                    "sample_rate_hz",
                    "samples",
                ],
            )
            writer.writeheader()
            for index in range(6):
                writer.writerow(
                    {
                        "record_id": f"regular-{index}",
                        "group_id": f"p-{index}",
                        "label": 0,
                        "sample_rate_hz": 25,
                        "samples": json.dumps(build_ppg_window(irregular=False)),
                    }
                )
            for index in range(6):
                writer.writerow(
                    {
                        "record_id": f"irregular-{index}",
                        "group_id": f"q-{index}",
                        "label": 1,
                        "sample_rate_hz": 25,
                        "samples": json.dumps(build_ppg_window(irregular=True)),
                    }
                )

        call_command("train_ppg_af_model", csv=str(csv_path), output=str(model_path))

        self.assertTrue(model_path.exists())

    def test_train_structured_af_model_command_writes_model_artifact(self):
        if importlib.util.find_spec("sklearn") is None:
            self.skipTest("当前环境未安装 scikit-learn。")
        if importlib.util.find_spec("lightgbm") is None:
            self.skipTest("当前环境未安装 lightgbm。")

        csv_path = workspace_temp_path("structured_windows.csv")
        model_path = workspace_temp_path("structured_af_model.pkl")
        report_path = workspace_temp_path("structured_af_report.json")
        for path in [csv_path, model_path, report_path]:
            if path.exists():
                path.unlink()

        fieldnames = [
            "patient_id",
            "group_id",
            "record_id",
            "window_start_sec",
            "window_end_sec",
            "sample_rate_hz",
            "label",
            "af_ratio",
            "ambiguous_ratio",
            "duration_seconds",
            "hr_mean",
            "hr_min",
            "hr_max",
            "hr_std",
            "ibi_mean",
            "ibi_std",
            "ibi_cv",
            "rmssd",
            "pnn50",
            "tachycardia_ratio",
            "bradycardia_ratio",
            "irregular_ratio",
            "peak_count",
            "peak_density",
            "flat_ratio",
        ]
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for index in range(6):
                writer.writerow(
                    {
                        "patient_id": f"patient-a-{index}",
                        "group_id": f"patient-a-{index}",
                        "record_id": f"window-a-{index}",
                        "window_start_sec": index * 30,
                        "window_end_sec": (index + 1) * 30,
                        "sample_rate_hz": 25,
                        "label": 0,
                        "af_ratio": 0.0,
                        "ambiguous_ratio": 0.0,
                        "duration_seconds": 30,
                        "hr_mean": 72 + index,
                        "hr_min": 68 + index,
                        "hr_max": 76 + index,
                        "hr_std": 1.8,
                        "ibi_mean": 0.82,
                        "ibi_std": 0.02,
                        "ibi_cv": 0.024,
                        "rmssd": 0.03,
                        "pnn50": 0.02,
                        "tachycardia_ratio": 0.0,
                        "bradycardia_ratio": 0.0,
                        "irregular_ratio": 0.04,
                        "peak_count": 36,
                        "peak_density": 1.2,
                        "flat_ratio": 0.08,
                    }
                )
            for index in range(6):
                writer.writerow(
                    {
                        "patient_id": f"patient-b-{index}",
                        "group_id": f"patient-b-{index}",
                        "record_id": f"window-b-{index}",
                        "window_start_sec": index * 30,
                        "window_end_sec": (index + 1) * 30,
                        "sample_rate_hz": 25,
                        "label": 1,
                        "af_ratio": 0.9,
                        "ambiguous_ratio": 0.0,
                        "duration_seconds": 30,
                        "hr_mean": 122 + index,
                        "hr_min": 88 + index,
                        "hr_max": 145 + index,
                        "hr_std": 16.5,
                        "ibi_mean": 0.58,
                        "ibi_std": 0.11,
                        "ibi_cv": 0.19,
                        "rmssd": 0.14,
                        "pnn50": 0.62,
                        "tachycardia_ratio": 0.72,
                        "bradycardia_ratio": 0.0,
                        "irregular_ratio": 0.68,
                        "peak_count": 61,
                        "peak_density": 2.03,
                        "flat_ratio": 0.02,
                    }
                )

        call_command(
            "train_structured_af_model",
            csv=str(csv_path),
            output=str(model_path),
            report=str(report_path),
        )

        self.assertTrue(model_path.exists())
        self.assertTrue(report_path.exists())
        with model_path.open("rb") as handle:
            artifact = pickle.load(handle)
        self.assertEqual(artifact["model_name"], "lightgbm")
        self.assertIn("baseline_metrics", artifact)
        self.assertIn("hist-gradient-boosting", artifact["baseline_metrics"])
        self.assertIn("logistic-regression", artifact["baseline_metrics"])
        with report_path.open("r", encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["model_name"], "lightgbm")
        self.assertIn("baseline_metrics", report)
        with override_settings(
            DEFAULT_STRUCTURED_AF_MODEL_PATH=str(model_path),
            STRUCTURED_AF_MIN_HISTORY_SAMPLES=5,
        ):
            payload = analyze_structured_measurement_window(
                measurements=[
                    type("M", (), {"heart_rate": value})()
                    for value in [76, 82, 97, 118, 129]
                ],
                duration_seconds=1800,
            )
        self.assertTrue(payload["available"])
        self.assertEqual(payload["model_name"], "lightgbm")
        self.assertIn("probability", payload)

    def test_prepare_cpsc2021_rr_af_csv_outputs_structured_columns(self):
        import numpy as np

        output_path = workspace_temp_path("cpsc2021_rr_windows.csv")
        fake_data_dir = workspace_temp_path("cpsc2021-fixture")
        fake_data_dir.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()

        class FakeRecord:
            fs = 200
            sig_len = 12000
            p_signal = np.ones((12000, 1))

        class FakeAnnotation:
            sample = [0, 6000]
            symbol = ["N", "N"]
            aux_note = ["(AFIB", "(N"]

        class FakeProcessing:
            @staticmethod
            def xqrs_detect(sig, fs, verbose=False):
                return [
                    200,
                    400,
                    600,
                    800,
                    1000,
                    1200,
                    1400,
                    1600,
                    1800,
                    2000,
                    2200,
                    2400,
                ]

        class FakeWfdb:
            @staticmethod
            def rdrecord(record_name, channels=None):
                return FakeRecord()

            @staticmethod
            def rdann(record_name, extension):
                return FakeAnnotation()

        with (
            patch.object(
                cpsc_command,
                "_discover_record_paths",
                return_value=[fake_data_dir / "A01"],
            ),
            patch.object(
                cpsc_command,
                "_import_wfdb",
                return_value=(FakeWfdb, FakeProcessing),
            ),
        ):
            call_command(
                "prepare_cpsc2021_rr_af_csv",
                data_dir=str(fake_data_dir),
                output=str(output_path),
                window_seconds=30,
                stride_seconds=30,
                min_rr_intervals=5,
            )

        self.assertTrue(output_path.exists())
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertNotIn("samples", reader.fieldnames)
            self.assertIn("hr_mean", reader.fieldnames)
            self.assertIn("ibi_mean", reader.fieldnames)
            self.assertIn("peak_density", reader.fieldnames)
            rows = list(reader)
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn(rows[0]["label"], {"0", "1"})

    def test_train_cpsc2021_rr_experiment_command_writes_model_and_report(self):
        if importlib.util.find_spec("sklearn") is None:
            self.skipTest("当前环境未安装 scikit-learn。")
        if importlib.util.find_spec("lightgbm") is None:
            self.skipTest("当前环境未安装 lightgbm。")

        csv_path = workspace_temp_path("cpsc2021_windows.csv")
        model_path = workspace_temp_path("cpsc2021_rr_experiment.pkl")
        report_path = workspace_temp_path("cpsc2021_rr_report.json")
        for path in [csv_path, model_path, report_path]:
            if path.exists():
                path.unlink()

        fieldnames = [
            "patient_id",
            "group_id",
            "record_id",
            "window_start_sec",
            "window_end_sec",
            "sample_rate_hz",
            "label",
            "af_ratio",
            "ambiguous_ratio",
            "duration_seconds",
            "hr_mean",
            "hr_min",
            "hr_max",
            "hr_std",
            "ibi_mean",
            "ibi_std",
            "ibi_cv",
            "rmssd",
            "pnn50",
            "tachycardia_ratio",
            "bradycardia_ratio",
            "irregular_ratio",
            "peak_count",
            "peak_density",
            "flat_ratio",
        ]
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for index in range(6):
                writer.writerow(
                    {
                        "patient_id": f"normal-{index}",
                        "group_id": f"normal-{index}",
                        "record_id": f"normal-{index}",
                        "window_start_sec": index * 30,
                        "window_end_sec": (index + 1) * 30,
                        "sample_rate_hz": 200,
                        "label": 0,
                        "af_ratio": 0.0,
                        "ambiguous_ratio": 0.0,
                        "duration_seconds": 30,
                        "hr_mean": 70 + index,
                        "hr_min": 67 + index,
                        "hr_max": 73 + index,
                        "hr_std": 1.6,
                        "ibi_mean": 0.84,
                        "ibi_std": 0.02,
                        "ibi_cv": 0.02,
                        "rmssd": 0.03,
                        "pnn50": 0.01,
                        "tachycardia_ratio": 0.0,
                        "bradycardia_ratio": 0.0,
                        "irregular_ratio": 0.03,
                        "peak_count": 35,
                        "peak_density": 1.16,
                        "flat_ratio": 0.02,
                    }
                )
            for index in range(6):
                writer.writerow(
                    {
                        "patient_id": f"af-{index}",
                        "group_id": f"af-{index}",
                        "record_id": f"af-{index}",
                        "window_start_sec": index * 30,
                        "window_end_sec": (index + 1) * 30,
                        "sample_rate_hz": 200,
                        "label": 1,
                        "af_ratio": 0.9,
                        "ambiguous_ratio": 0.0,
                        "duration_seconds": 30,
                        "hr_mean": 124 + index,
                        "hr_min": 82 + index,
                        "hr_max": 148 + index,
                        "hr_std": 18.0,
                        "ibi_mean": 0.56,
                        "ibi_std": 0.12,
                        "ibi_cv": 0.21,
                        "rmssd": 0.16,
                        "pnn50": 0.68,
                        "tachycardia_ratio": 0.74,
                        "bradycardia_ratio": 0.0,
                        "irregular_ratio": 0.71,
                        "peak_count": 62,
                        "peak_density": 2.06,
                        "flat_ratio": 0.01,
                    }
                )

        call_command(
            "train_cpsc2021_rr_experiment",
            csv=str(csv_path),
            output=str(model_path),
            report=str(report_path),
        )

        self.assertTrue(model_path.exists())
        self.assertTrue(report_path.exists())
        with report_path.open("r", encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["model_name"], "lightgbm")
        self.assertIn("hist-gradient-boosting", report["baseline_metrics"])

    @override_settings(STRUCTURED_AF_MIN_HISTORY_SAMPLES=5)
    def test_packet_ingest_keeps_rules_when_structured_model_missing(self):
        missing_model_path = (
            Path(__file__).resolve().parent.parent
            / ".tmp-tests"
            / "structured-af-missing-test.pkl"
        )
        missing_model_path.parent.mkdir(parents=True, exist_ok=True)
        if missing_model_path.exists():
            missing_model_path.unlink()

        with override_settings(
            DEFAULT_STRUCTURED_AF_MODEL_PATH=str(missing_model_path)
        ):
            response = None
            for index, heart_rate in enumerate([76, 82, 118, 121, 124]):
                response = self.client.post(
                    "/api/v1/packets",
                    {
                        "device_id": "ring-001",
                        "client_time": f"2026-03-15T18:{index:02d}:00+08:00",
                        "source": "wechat-miniapp",
                        "payload": {
                            "frame_hex": build_heart_rate_frame_hex(
                                heart_rate, hrv=28 + index, stress=36 + index
                            ),
                        },
                    },
                    format="json",
                )

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["analysis"]["algorithm_version"], "structured-ml-primary-v1"
        )
        self.assertIn(
            "window_repeated_tachycardia_30m", response.data["analysis"]["triggers"]
        )
        self.assertIn("ml", response.data["analysis"]["details"])
        self.assertTrue(response.data["analysis"]["details"]["ml"]["enabled"])
        self.assertFalse(response.data["analysis"]["details"]["ml"]["available"])
        self.assertEqual(
            response.data["analysis"]["details"]["ml"]["skip_reason"], "model_not_found"
        )
        self.assertIn(
            "机器学习暂不可用，已使用规则引擎兜底", response.data["analysis"]["labels"]
        )

    @override_settings(STRUCTURED_AF_MIN_HISTORY_SAMPLES=5)
    def test_packet_ingest_includes_structured_ml_when_model_available(self):
        feature_names = [
            "duration_seconds",
            "hr_mean",
            "hr_min",
            "hr_max",
            "hr_std",
            "ibi_mean",
            "ibi_std",
            "ibi_cv",
            "rmssd",
            "pnn50",
            "tachycardia_ratio",
            "bradycardia_ratio",
            "irregular_ratio",
            "peak_count",
            "peak_density",
            "flat_ratio",
        ]
        artifact = {
            "model_name": "dummy-structured-af",
            "model_version": "structured-af-test",
            "feature_names": feature_names,
            "decision_threshold": 0.6,
            "estimator": DummyStructuredAfEstimator(),
            "metrics": {"auroc": 0.8},
        }

        model_path = workspace_temp_path("structured_af_model_available.pkl")
        if model_path.exists():
            model_path.unlink()
        with model_path.open("wb") as handle:
            pickle.dump(artifact, handle)

        with override_settings(DEFAULT_STRUCTURED_AF_MODEL_PATH=str(model_path)):
            response = None
            for index, heart_rate in enumerate([78, 84, 89, 96, 132]):
                response = self.client.post(
                    "/api/v1/packets",
                    {
                        "device_id": "ring-001",
                        "client_time": f"2026-03-15T19:{index:02d}:00+08:00",
                        "source": "wechat-miniapp",
                        "payload": {
                            "frame_hex": build_heart_rate_frame_hex(
                                heart_rate, hrv=25 + index, stress=30 + index
                            ),
                        },
                    },
                    format="json",
                )

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ml_details = response.data["analysis"]["details"]["ml"]
        self.assertTrue(ml_details["enabled"])
        self.assertTrue(ml_details["available"])
        self.assertEqual(ml_details["model_version"], "structured-af-test")
        self.assertTrue(ml_details["label"])
        self.assertEqual(ml_details["feature_source"], "measurement_window")
        self.assertIn("probability", ml_details)
        self.assertIn("features", ml_details)
        self.assertIn(
            "ml_structured_af_positive", response.data["analysis"]["triggers"]
        )
        self.assertEqual(response.data["analysis"]["risk_level"], "critical")
        self.assertEqual(response.data["analysis"]["risk_score"], 0.88)


# Create your tests here.
