from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase


class LoginApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='alice',
            password='pass12345',
        )

    def test_login_returns_token(self):
        response = self.client.post(
            '/api/v1/auth/login',
            {'username': 'alice', 'password': 'pass12345'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], self.user.username)


class UserManagementApiTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='manager',
            password='pass12345',
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
                'is_staff': False,
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(get_user_model().objects.filter(username='patient-b').exists())

# Create your tests here.
