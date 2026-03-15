from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import DeviceBinding


class DeviceBindApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='bind-user',
            password='pass12345',
        )
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_bind_device_creates_active_binding(self):
        response = self.client.post(
            '/api/v1/devices/bind',
            {
                'device_id': 'ring-001',
                'name': 'Smart Ring',
                'alias': '我的戒指',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            DeviceBinding.objects.filter(
                user=self.user,
                device__device_id='ring-001',
                is_active=True,
            ).exists()
        )

    def test_device_list_returns_bound_devices(self):
        self.client.post(
            '/api/v1/devices/bind',
            {
                'device_id': 'ring-001',
                'name': 'Smart Ring',
                'alias': '我的戒指',
            },
            format='json',
        )

        response = self.client.get('/api/v1/devices/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['device_id'], 'ring-001')

# Create your tests here.
