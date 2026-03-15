from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from unittest.mock import patch


class LoginApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='alice',
            password='pass12345',
        )

    def test_login_returns_token(self):
        response = self.client.post(
            '/api/v1/auth/login',
            {
                'username': 'alice',
                'password': 'pass12345',
                'login_context': {
                    'ip': '8.8.8.8',
                    'city': 'Beijing',
                    'region': 'Beijing',
                    'country_name': 'China',
                    'latitude': 39.9042,
                    'longitude': 116.4074,
                },
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], self.user.username)
        self.assertEqual(response.data['user']['last_login_location']['city'], 'Beijing')
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_login_city, 'Beijing')
        self.assertEqual(self.user.last_login_ip, '8.8.8.8')

    def test_login_falls_back_to_server_side_lookup_without_login_context(self):
        with patch(
            'accounts.location.resolve_ip_location',
            return_value={
                'country': 'China',
                'region': 'Guangdong',
                'city': 'Shenzhen',
                'latitude': 22.5431,
                'longitude': 114.0579,
                'label': 'China / Guangdong / Shenzhen',
                'resolved': True,
            },
        ):
            response = self.client.post(
                '/api/v1/auth/login',
                {'username': 'alice', 'password': 'pass12345'},
                format='json',
                REMOTE_ADDR='8.8.4.4',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['last_login_location']['city'], 'Shenzhen')

    def test_console_login_rejects_non_admin(self):
        response = self.client.post(
            '/api/v1/auth/console-login',
            {'username': 'alice', 'password': 'pass12345'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UserManagementApiTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='manager',
            password='pass12345',
            role=get_user_model().Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        token = Token.objects.create(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_admin_can_list_users(self):
        get_user_model().objects.create_user(username='patient', password='pass12345')

        response = self.client.get('/api/v1/auth/users')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

    def test_admin_can_create_user(self):
        response = self.client.post(
            '/api/v1/auth/users',
            {
                'username': 'patient-b',
                'password': 'pass12345',
                'email': 'patient@example.com',
                'first_name': 'Patient',
                'last_name': 'B',
                'is_active': True,
                'generate_china_location': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(get_user_model().objects.filter(username='patient-b').exists())
        user = get_user_model().objects.get(username='patient-b')
        self.assertEqual(user.last_login_country, 'China')
        self.assertTrue(user.last_login_ip)

    def test_admin_can_batch_create_users(self):
        response = self.client.post(
            '/api/v1/auth/users/batch',
            {
                'count': 3,
                'username_prefix': 'patient',
                'password': 'pass12345',
                'role': 'user',
                'generate_china_location': True,
                'generate_profile': True,
                'email_domain': 'demo.local',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 3)
        created_users = get_user_model().objects.filter(username__startswith='patient')
        self.assertEqual(created_users.count(), 3)
        self.assertTrue(all(user.last_login_country == 'China' for user in created_users))

    def test_admin_can_delete_user(self):
        user = get_user_model().objects.create_user(username='patient-c', password='pass12345')

        response = self.client.delete(f'/api/v1/auth/users/{user.pk}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(get_user_model().objects.filter(pk=user.pk).exists())

    def test_admin_cannot_delete_self(self):
        response = self.client.delete(f'/api/v1/auth/users/{self.admin.pk}')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_batch_delete_users(self):
        users = [
            get_user_model().objects.create_user(username='remove-a', password='pass12345'),
            get_user_model().objects.create_user(username='remove-b', password='pass12345'),
        ]

        response = self.client.post(
            '/api/v1/auth/users/batch-delete',
            {'user_ids': [user.pk for user in users]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_count'], 2)
        self.assertFalse(get_user_model().objects.filter(username__in=['remove-a', 'remove-b']).exists())

# Create your tests here.
