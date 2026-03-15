from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from devices.models import Device, DeviceBinding

from .models import AlertEvent, RawPacket
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
        self.assertTrue(response.data['alert_state']['has_alert'])
        self.assertEqual(RawPacket.objects.count(), 1)
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

# Create your tests here.
