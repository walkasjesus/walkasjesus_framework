from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
	EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
	DEFAULT_FROM_EMAIL='noreply@example.com',
	ACCOUNT_MODERATOR_EMAILS=['moderator@example.com'],
	ACCOUNT_EMAIL_FAIL_SILENTLY=False,
)
class SignupActivationTests(TestCase):
	def setUp(self):
		self.signup_url = reverse('account:signup')

	def _signup_data(self, username='newuser', email='newuser@example.com'):
		return {
			'username': username,
			'first_name': 'New',
			'last_name': 'User',
			'email': email,
			'password1': 'StrongPass123!',
			'password2': 'StrongPass123!',
			'agree_toc': True,
		}

	def _get_activation_email(self):
		for sent_message in mail.outbox:
			if sent_message.to == ['newuser@example.com']:
				return sent_message
		self.fail('Activation email was not sent to the registered user.')

	def test_signup_creates_inactive_user_and_sends_notifications(self):
		response = self.client.post(self.signup_url, data=self._signup_data())

		self.assertRedirects(response, reverse('account:login'))

		user = User.objects.get(username='newuser')
		self.assertFalse(user.is_active)

		self.assertEqual(len(mail.outbox), 2)
		activation_email = self._get_activation_email()
		self.assertIn('/account/activate/', activation_email.body)

		moderator_email = next(
			sent_message for sent_message in mail.outbox if sent_message.to == ['moderator@example.com']
		)
		self.assertIn('newuser', moderator_email.body)
		self.assertIn('newuser@example.com', moderator_email.body)

	def test_activation_link_activates_user(self):
		self.client.post(self.signup_url, data=self._signup_data())
		activation_email = self._get_activation_email()

		activation_link = next(
			line.strip() for line in activation_email.body.splitlines() if '/account/activate/' in line
		)
		activation_path = urlparse(activation_link).path
		response = self.client.get(activation_path)

		self.assertRedirects(response, reverse('account:login'))
		user = User.objects.get(username='newuser')
		self.assertTrue(user.is_active)
