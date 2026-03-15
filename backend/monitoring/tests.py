from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from devices.models import Device, DeviceBinding

from .models import AiSettings, AlertEvent, Measurement, RawPacket
from .services import parse_packet


class PacketParserTests(APITestCase):
    def test_parse_heart_rate_packet(self):
        result = parse_packet(
            {
                'frame_hex': '00 00 31 00 03 48 24 50 8E 0E',
            }
        )

        self.assertEqual(result.packet_kind, 'heart_rate')
        self.assertEqual(result.parsed['heartRate'], 72)
        self.assertEqual(result.parsed['hrv'], 36)
        self.assertEqual(result.parsed['stress'], 80)
        self.assertAlmostEqual(result.parsed['temperature'], 37.26, places=2)

    def test_generate_mock_monitoring_data_command_creates_measurements(self):
        call_command(
            'generate_mock_monitoring_data',
            username='cmd-user',
            device_id='cmd-ring-001',
            scenario='trend',
            count=4,
            interval_minutes=30,
        )

        self.assertTrue(get_user_model().objects.filter(username='cmd-user').exists())
        self.assertTrue(Device.objects.filter(device_id='cmd-ring-001').exists())
        self.assertGreater(Measurement.objects.filter(device__device_id='cmd-ring-001').count(), 0)


class PacketIngestApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='monitor-user',
            password='pass12345',
        )
        self.device = Device.objects.create(device_id='ring-001', source='wechat-miniapp')
        DeviceBinding.objects.create(user=self.user, device=self.device)
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_packet_ingest_preserves_raw_payload_and_returns_analysis(self):
        self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-001',
                'client_time': '2026-03-15T14:20:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {
                    'frame_hex': '00 00 31 00 03 5A 18 20 6E 0E',
                },
            },
            format='json',
        )
        payload = {
            'device_id': 'ring-001',
            'client_time': '2026-03-15T14:30:00+08:00',
            'source': 'wechat-miniapp',
            'payload': {
                'frame_hex': '00 00 31 00 03 78 28 55 8E 0E',
                'frame_bytes': [0, 0, 49, 0, 3, 120, 40, 85, 142, 14],
            },
        }

        response = self.client.post('/api/v1/packets', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['raw_payload']['payload'], payload['payload'])
        self.assertEqual(response.data['parsed']['heartRate'], 120)
        self.assertTrue(response.data['analysis']['should_alert'])
        self.assertEqual(response.data['analysis']['algorithm_version'], 'rules-window-baseline-v2')
        self.assertIn('details', response.data['analysis'])
        self.assertTrue(response.data['alert_state']['has_alert'])
        self.assertGreaterEqual(RawPacket.objects.count(), 2)
        self.assertEqual(AlertEvent.objects.count(), 1)

    def test_measurement_queries_and_alert_read(self):
        self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-001',
                'client_time': '2026-03-15T14:31:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {
                    'frame_hex': '00 00 31 00 03 78 28 55 8E 0E',
                },
            },
            format='json',
        )

        list_response = self.client.get('/api/v1/measurements?device_id=ring-001')
        latest_response = self.client.get('/api/v1/measurements/latest?device_id=ring-001')
        alerts_response = self.client.get('/api/v1/alerts?device_id=ring-001')

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(latest_response.status_code, status.HTTP_200_OK)
        self.assertEqual(alerts_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(len(alerts_response.data), 1)

        alert_id = alerts_response.data[0]['id']
        read_response = self.client.post(f'/api/v1/alerts/{alert_id}/read', {}, format='json')
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertTrue(read_response.data['is_read'])

    def test_device_status_returns_latest_measurement(self):
        self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-001',
                'client_time': '2026-03-15T14:31:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {
                    'frame_hex': '00 00 12 00 64',
                },
            },
            format='json',
        )

        response = self.client.get('/api/v1/devices/ring-001/status')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['device_id'], 'ring-001')
        self.assertEqual(response.data['latest_measurement']['parsed']['batteryLevel'], 100)

    def test_dashboard_overview_returns_counts(self):
        self.user.last_login_ip = '1.1.1.1'
        self.user.last_login_country = 'China'
        self.user.last_login_region = 'Beijing'
        self.user.last_login_city = 'Beijing'
        self.user.last_login_latitude = 39.9042
        self.user.last_login_longitude = 116.4074
        self.user.save(
            update_fields=[
                'last_login_ip',
                'last_login_country',
                'last_login_region',
                'last_login_city',
                'last_login_latitude',
                'last_login_longitude',
            ]
        )

        self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-001',
                'client_time': '2026-03-15T14:31:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {
                    'frame_hex': '00 00 31 00 03 78 28 55 8E 0E',
                },
            },
            format='json',
        )

        response = self.client.get('/api/v1/dashboard/overview')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['counts']['devices'], 1)
        self.assertEqual(response.data['counts']['measurements'], 1)
        self.assertGreaterEqual(response.data['counts']['alerts'], 1)
        self.assertEqual(response.data['user_summaries'][0]['last_login_location']['city'], 'Beijing')

    def test_analysis_v2_detects_window_and_baseline_flags(self):
        for minute_value, frame_hex in [
            (0, '00 00 31 00 03 5A 10 10 60 0E'),
            (35, '00 00 31 00 03 78 28 40 70 0E'),
            (45, '00 00 31 00 03 79 29 45 72 0E'),
        ]:
            self.client.post(
                '/api/v1/packets',
                {
                    'device_id': 'ring-001',
                    'client_time': f'2026-03-15T14:{minute_value:02d}:00+08:00',
                    'source': 'wechat-miniapp',
                    'payload': {'frame_hex': frame_hex},
                },
                format='json',
            )

        response = self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-001',
                'client_time': '2026-03-15T14:59:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {'frame_hex': '00 00 31 00 03 82 30 55 68 0E'},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        triggers = response.data['analysis']['triggers']
        self.assertIn('window_repeated_tachycardia_30m', triggers)
        self.assertIn('baseline_heart_rate_above_personal_baseline', triggers)
        self.assertIn('window_stats', response.data['analysis']['details'])
        self.assertIn('baselines', response.data['analysis']['details'])

    def test_measurement_llm_insight_returns_prompt_when_provider_disabled(self):
        ingest = self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-001',
                'client_time': '2026-03-15T15:00:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {'frame_hex': '00 00 31 00 03 78 28 55 8E 0E'},
            },
            format='json',
        )

        response = self.client.post(f"/api/v1/measurements/{ingest.data['id']}/llm-insight", {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['available'])
        self.assertIn('prompt', response.data)
        self.assertIn('context', response.data)
        self.assertEqual(response.data['source'], 'template')

    def test_measurement_trends_returns_daily_and_weekly_stats(self):
        for timestamp, frame_hex in [
            ('2026-03-10T10:00:00+08:00', '00 00 31 00 03 60 20 20 70 0E'),
            ('2026-03-15T10:00:00+08:00', '00 00 31 00 03 78 28 55 8E 0E'),
        ]:
            self.client.post(
                '/api/v1/packets',
                {
                    'device_id': 'ring-001',
                    'client_time': timestamp,
                    'source': 'wechat-miniapp',
                    'payload': {'frame_hex': frame_hex},
                },
                format='json',
            )

        response = self.client.get('/api/v1/measurements/trends')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('daily', response.data)
        self.assertIn('weekly', response.data)
        self.assertEqual(len(response.data['daily']), 7)
        self.assertEqual(len(response.data['weekly']), 8)

    def test_admin_can_update_ai_settings(self):
        admin = get_user_model().objects.create_user(
            username='manager',
            password='pass12345',
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {admin_token.key}')

        response = self.client.put(
            '/api/v1/ai/settings',
            {
                'enabled': True,
                'mode': 'template',
                'model': 'gpt-5.2',
                'system_prompt': 'test prompt',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        settings_obj = AiSettings.objects.get(singleton_key='default')
        self.assertTrue(settings_obj.enabled)
        self.assertEqual(settings_obj.mode, 'template')
        self.assertEqual(settings_obj.system_prompt, 'test prompt')

    def test_admin_can_test_ai_settings_with_template_mode(self):
        admin = get_user_model().objects.create_user(
            username='manager-test',
            password='pass12345',
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {admin_token.key}')

        response = self.client.post(
            '/api/v1/ai/settings/test',
            {
                'enabled': True,
                'mode': 'template',
                'model': 'gpt-4o-mini',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['ok'])
        self.assertEqual(response.data['source'], 'template')
        self.assertIn('结果解读', response.data['content'])

    def test_staff_can_scope_dashboard_by_user(self):
        other_user = get_user_model().objects.create_user(
            username='other-user',
            password='pass12345',
        )
        other_device = Device.objects.create(device_id='ring-002', source='wechat-miniapp')
        DeviceBinding.objects.create(user=other_user, device=other_device)

        self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-001',
                'client_time': '2026-03-15T14:31:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {'frame_hex': '00 00 12 00 64'},
            },
            format='json',
        )

        admin = get_user_model().objects.create_user(
            username='manager',
            password='pass12345',
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {admin_token.key}')

        self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-002',
                'client_time': '2026-03-15T14:32:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {'frame_hex': '00 00 12 00 32'},
            },
            format='json',
        )

        global_response = self.client.get('/api/v1/dashboard/overview')
        scoped_response = self.client.get(f'/api/v1/dashboard/overview?user_id={self.user.id}')

        self.assertEqual(global_response.status_code, status.HTTP_200_OK)
        self.assertEqual(global_response.data['counts']['devices'], 2)
        self.assertEqual(scoped_response.status_code, status.HTTP_200_OK)
        self.assertEqual(scoped_response.data['counts']['devices'], 1)

    def test_admin_accounts_are_excluded_from_global_monitoring_views(self):
        admin = get_user_model().objects.create_user(
            username='manager',
            password='pass12345',
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
            last_login_ip='39.100.10.10',
            last_login_country='China',
            last_login_region='北京市',
            last_login_city='北京市',
            last_login_latitude=39.9042,
            last_login_longitude=116.4074,
        )
        admin_device = Device.objects.create(device_id='ring-admin', source='wechat-miniapp')
        DeviceBinding.objects.create(user=admin, device=admin_device)

        admin_token = Token.objects.create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {admin_token.key}')
        self.client.post(
            '/api/v1/packets',
            {
                'device_id': 'ring-admin',
                'client_time': '2026-03-15T14:40:00+08:00',
                'source': 'wechat-miniapp',
                'payload': {'frame_hex': '00 00 12 00 64'},
            },
            format='json',
        )

        response = self.client.get('/api/v1/dashboard/overview')
        measurements_response = self.client.get('/api/v1/measurements')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['counts']['devices'], 1)
        self.assertEqual(len(response.data['user_summaries']), 1)
        self.assertEqual(response.data['user_summaries'][0]['username'], self.user.username)
        self.assertEqual(measurements_response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(item['username'] != 'manager' for item in measurements_response.data))

# Create your tests here.
