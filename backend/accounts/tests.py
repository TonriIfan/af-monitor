from django.contrib.auth import get_user_model
from rest_framework import status
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

# Create your tests here.
