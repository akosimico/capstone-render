from django.test import TestCase
from authentication.models import UserProfile
from authentication.utils.tokens import make_dashboard_token, parse_dashboard_token
from django.contrib.auth.models import User
from django.core.signing import SignatureExpired, BadSignature
from time import sleep

class DashboardTokenUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="bob_test", password="test123")
        cls.profile, _ = UserProfile.objects.get_or_create(
            user=cls.user, defaults={"full_name": "Bob Builder", "role": "OM"}
        )

    def test_token_creation_and_parsing(self):
        token = make_dashboard_token(self.profile)
        data = parse_dashboard_token(token)
        self.assertEqual(data["u"], str(self.profile.uuid))
        self.assertEqual(data["r"], self.profile.role)
        self.assertEqual(data["v"], self.profile.token_version)

    def test_tampered_token_fails(self):
        token = make_dashboard_token(self.profile)
        tampered = token[:-2] + "xx"
        with self.assertRaises(BadSignature):
            parse_dashboard_token(tampered)

    def test_expired_token(self):
        token = make_dashboard_token(self.profile)
        sleep(2)  # wait for token to expire
        with self.assertRaises(SignatureExpired):
            parse_dashboard_token(token, max_age=1)

    # Make it an instance method by adding self
    def validate_role(self, token, expected_role):
        data = parse_dashboard_token(token)
        return data["r"] == expected_role

    def test_role_validation(self):
        token = make_dashboard_token(self.profile)
        self.assertTrue(self.validate_role(token, "OM"))
        self.assertFalse(self.validate_role(token, "PM"))
