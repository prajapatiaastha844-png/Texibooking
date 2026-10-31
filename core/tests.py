import re
from datetime import timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.test.utils import captured_stdout
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AdminAccount,
    AdminPasswordResetOTP,
    Booking,
    CustomerPasswordResetOTP,
    Driver,
    DriverPasswordResetOTP,
    Taxi,
    User as CustomerUser,
)


class TaxiModelTests(TestCase):
    def test_taxi_fields_and_driver_relationship(self):
        driver = Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='driver-password',
        )

        taxi = Taxi.objects.create(
            number='CAB-123',
            type='Sedan',
            source='Downtown',
            destination='Airport',
            price='25.50',
            availability=True,
            driver=driver,
        )

        self.assertEqual(taxi.driver, driver)
        self.assertEqual(driver.taxis.get(), taxi)
        self.assertEqual(str(taxi), 'CAB-123')


class DriverModelTests(TestCase):
    def test_save_normalizes_driver_details_and_hashes_password(self):
        driver = Driver(
            name='  Morgan Driver  ',
            email='  MORGAN@EXAMPLE.COM ',
            license_number=' DL-123456 ',
            mobile='+1 (555) 987-6543',
            password='driver-password',
        )

        driver.save()

        self.assertEqual(driver.name, 'Morgan Driver')
        self.assertEqual(driver.email, 'morgan@example.com')
        self.assertEqual(driver.license_number, 'DL-123456')
        self.assertEqual(driver.mobile, '+15559876543')
        self.assertNotEqual(driver.password, 'driver-password')
        self.assertTrue(driver.check_password('driver-password'))

    def test_save_rejects_invalid_driver_data(self):
        driver = Driver(
            name='Morgan Driver',
            email='not-an-email',
            license_number='DL-123456',
            mobile='555-abc-1234',
            password='driver-password',
        )

        with self.assertRaises(ValidationError):
            driver.save()

        self.assertEqual(Driver.objects.count(), 0)

    def test_save_rejects_case_insensitive_email_and_license_duplicates(self):
        Driver.objects.create(
            name='Existing Driver',
            email='existing@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='first-password',
        )

        for email, license_number in (
            ('EXISTING@example.com', 'DL-654321'),
            ('new@example.com', 'dl-123456'),
        ):
            with self.subTest(email=email, license_number=license_number):
                driver = Driver(
                    name='New Driver',
                    email=email,
                    license_number=license_number,
                    mobile='5551234567',
                    password='second-password',
                )
                with self.assertRaises(ValidationError):
                    driver.save()

        self.assertEqual(Driver.objects.count(), 1)

    def test_driver_fields_and_password_hashing(self):
        driver = Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='driver-password',
        )

        self.assertEqual(driver.name, 'Morgan Driver')
        self.assertEqual(driver.email, 'morgan@example.com')
        self.assertEqual(driver.license_number, 'DL-123456')
        self.assertEqual(driver.mobile, '5559876543')
        self.assertNotEqual(driver.password, 'driver-password')
        self.assertTrue(driver.check_password('driver-password'))
        self.assertFalse(driver.check_password('wrong-password'))

        driver.save()
        self.assertTrue(driver.check_password('driver-password'))

    def test_driver_email_and_license_number_must_be_unique(self):
        Driver.objects.create(
            name='First Driver',
            email='same@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='first-password',
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Driver.objects.create(
                    name='Second Driver',
                    email='same@example.com',
                    license_number='DL-654321',
                    mobile='5551234567',
                    password='second-password',
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Driver.objects.create(
                    name='Third Driver',
                    email='third@example.com',
                    license_number='DL-123456',
                    mobile='5551234567',
                    password='third-password',
                )


class DriverRegistrationTests(TestCase):
    def test_driver_registration_page_shows_all_requested_fields(self):
        response = self.client.get(reverse('driver_register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create your driver account')
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="license_number"')
        self.assertContains(response, 'name="mobile"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, reverse('user_login'))
        self.assertContains(response, reverse('driver_login'))

    def test_driver_can_register_with_normalized_details_and_hashed_password(self):
        response = self.client.post(
            reverse('driver_register'),
            {
                'name': 'Morgan Driver',
                'email': '  MORGAN@example.com ',
                'license_number': ' DL-123456 ',
                'mobile': '+1 (555) 987-6543',
                'password': 'Strong-Driver-932!',
            },
            follow=True,
        )

        driver = Driver.objects.get()
        self.assertEqual(
            response.redirect_chain,
            [(reverse('driver_register'), 302)],
        )
        self.assertEqual(driver.name, 'Morgan Driver')
        self.assertEqual(driver.email, 'morgan@example.com')
        self.assertEqual(driver.license_number, 'DL-123456')
        self.assertEqual(driver.mobile, '+15559876543')
        self.assertNotEqual(driver.password, 'Strong-Driver-932!')
        self.assertTrue(driver.check_password('Strong-Driver-932!'))
        self.assertContains(
            response,
            'Your driver account has been created successfully.',
        )

    def test_driver_registration_rejects_duplicate_email_and_license(self):
        Driver.objects.create(
            name='Existing Driver',
            email='existing@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='Strong-Driver-932!',
        )

        submissions = (
            {
                'name': 'New Driver',
                'email': 'EXISTING@example.com',
                'license_number': 'DL-654321',
                'mobile': '5551234567',
                'password': 'Strong-New-Driver-932!',
            },
            {
                'name': 'New Driver',
                'email': 'new@example.com',
                'license_number': 'dl-123456',
                'mobile': '5551234567',
                'password': 'Strong-New-Driver-932!',
            },
        )

        for submission in submissions:
            with self.subTest(submission=submission):
                response = self.client.post(
                    reverse('driver_register'),
                    submission,
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Driver.objects.count(), 1)

    def test_driver_registration_rejects_invalid_phone_and_weak_password(self):
        invalid_submissions = (
            ('555-abc-1234', 'Strong-Driver-932!'),
            ('5551234567', 'password'),
        )

        for index, (mobile, password) in enumerate(invalid_submissions):
            with self.subTest(mobile=mobile, password=password):
                response = self.client.post(
                    reverse('driver_register'),
                    {
                        'name': 'New Driver',
                        'email': f'driver-{index}@example.com',
                        'license_number': f'DL-{index}23456',
                        'mobile': mobile,
                        'password': password,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Driver.objects.count(), 0)


class DriverLoginTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='Strong-Driver-932!',
        )

    def test_driver_login_page_shows_email_and_password_fields(self):
        response = self.client.get(reverse('driver_login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Driver sign in')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, reverse('driver_register'))
        self.assertContains(response, reverse('driver_forgot_password'))

    def test_driver_can_sign_in_and_view_account_details(self):
        response = self.client.post(
            reverse('driver_login'),
            {'email': 'MORGAN@example.com', 'password': 'Strong-Driver-932!'},
        )

        self.assertRedirects(response, reverse('driver_dashboard'))
        self.assertEqual(
            self.client.session['driver_user_id'],
            self.driver.pk,
        )
        response = self.client.get(reverse('driver_dashboard'))
        self.assertContains(response, 'Welcome back, Morgan Driver')
        self.assertContains(response, 'morgan@example.com')
        self.assertContains(response, 'DL-123456')
        self.assertContains(response, '5559876543')
        self.assertContains(response, 'Sign out')
        self.assertNotContains(response, 'Strong-Driver-932!')

    def test_driver_login_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse('driver_login'),
            {'email': 'morgan@example.com', 'password': 'incorrect-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid email or password.')
        self.assertNotIn('driver_user_id', self.client.session)

    def test_driver_dashboard_requires_a_valid_driver_session(self):
        response = self.client.get(reverse('driver_dashboard'))
        self.assertRedirects(response, reverse('driver_login'))

        session = self.client.session
        session['driver_user_id'] = self.driver.pk
        session.save()
        response = self.client.get(reverse('driver_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Morgan Driver')

        session = self.client.session
        session['driver_user_id'] = 99999
        session.save()
        response = self.client.get(reverse('driver_dashboard'))
        self.assertRedirects(response, reverse('driver_login'))
        self.assertNotIn('driver_user_id', self.client.session)

    def test_driver_dashboard_shows_only_bookings_assigned_to_driver(self):
        taxi = Taxi.objects.create(
            number='CAB-101',
            type='Sedan',
            source='Downtown',
            destination='Airport',
            price='25.50',
            driver=self.driver,
        )
        customer = CustomerUser.objects.create(
            name='Rider One',
            email='rider@example.com',
            mobile='5551234567',
            password='Strong-Pass-932!',
        )
        assigned_booking = Booking.objects.create(
            user=customer,
            taxi=taxi,
            status='Pending',
        )
        other_driver = Driver.objects.create(
            name='Other Driver',
            email='other@example.com',
            license_number='DL-654321',
            mobile='5557654321',
            password='Strong-Driver-932!',
        )
        other_taxi = Taxi.objects.create(
            number='CAB-102',
            type='SUV',
            source='Station',
            destination='Hotel',
            price='35.50',
            driver=other_driver,
        )
        Booking.objects.create(
            user=customer,
            taxi=other_taxi,
            status='Pending',
        )
        session = self.client.session
        session['driver_user_id'] = self.driver.pk
        session.save()

        response = self.client.get(reverse('driver_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['bookings']),
            [assigned_booking],
        )
        self.assertContains(response, '#{}'.format(assigned_booking.pk))
        self.assertNotContains(response, 'CAB-102')

    def test_driver_login_redirects_existing_session_to_dashboard(self):
        session = self.client.session
        session['driver_user_id'] = self.driver.pk
        session.save()

        response = self.client.get(reverse('driver_login'))

        self.assertRedirects(response, reverse('driver_dashboard'))

    def test_driver_can_sign_out_without_clearing_other_session_auth(self):
        self.client.force_login(
            get_user_model().objects.create_user(
                username='admin',
                password='admin-password',
                is_staff=True,
            )
        )
        session = self.client.session
        session['driver_user_id'] = self.driver.pk
        session['customer_user_id'] = 42
        session.save()

        response = self.client.post(reverse('driver_logout'), follow=True)

        self.assertRedirects(response, reverse('driver_login'))
        self.assertNotIn('driver_user_id', self.client.session)
        self.assertEqual(self.client.session['customer_user_id'], 42)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, 'signed out')

    def test_driver_logout_rejects_get_requests(self):
        response = self.client.get(reverse('driver_logout'))

        self.assertEqual(response.status_code, 405)


class DriverForgotPasswordTests(TestCase):
    def setUp(self):
        self.driver = Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='Strong-Driver-932!',
        )

    def test_forgot_password_page_has_email_field_and_back_link(self):
        response = self.client.get(reverse('driver_forgot_password'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Forgot your password?')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, reverse('driver_login'))

    def test_unknown_driver_email_gets_generic_response(self):
        response = self.client.post(
            reverse('driver_forgot_password'),
            {'email': 'unknown@example.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'If a driver account matches')
        self.assertEqual(DriverPasswordResetOTP.objects.count(), 0)
        self.assertNotIn('driver_password_reset_token', self.client.session)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    )
    def test_registered_driver_receives_reset_otp_in_console_email(self):
        with captured_stdout() as output:
            response = self.client.post(
                reverse('driver_forgot_password'),
                {'email': self.driver.email},
            )

        console_email = output.getvalue()
        self.assertEqual(response.status_code, 200)
        self.assertIn('From: admin@taxibooking.local', console_email)
        self.assertIn('To: morgan@example.com', console_email)
        self.assertIn('Taxi Booking driver password reset', console_email)
        self.assertRegex(console_email, r'reset code is \d{6}')

        challenge = DriverPasswordResetOTP.objects.get(driver=self.driver)
        otp = re.search(r'reset code is (\d{6})', console_email).group(1)
        self.assertNotEqual(challenge.otp_hash, otp)
        self.assertTrue(check_password(otp, challenge.otp_hash))
        self.assertEqual(
            self.client.session['driver_password_reset_token'],
            str(challenge.token),
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_driver_can_reset_password_with_email_code(self):
        response = self.client.post(
            reverse('driver_forgot_password'),
            {'email': 'MORGAN@example.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('driver_reset_otp'))
        challenge = DriverPasswordResetOTP.objects.get(driver=self.driver)
        self.assertEqual(mail.outbox[0].to, ['morgan@example.com'])
        otp = re.search(r'code is (\d{6})', mail.outbox[0].body).group(1)
        self.assertTrue(check_password(otp, challenge.otp_hash))

        reset_url = reverse('driver_reset_otp')
        response = self.client.post(reset_url, {'otp': otp})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your verification code has been confirmed.')
        self.assertContains(response, 'name="new_password1"')

        response = self.client.post(
            reset_url,
            {
                'new_password1': '12345678',
                'new_password2': '12345678',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This password is entirely numeric.')
        self.driver.refresh_from_db()
        challenge.refresh_from_db()
        self.assertTrue(self.driver.check_password('Strong-Driver-932!'))
        self.assertFalse(challenge.is_used)

        new_password = 'New-Driver-Password-723!'
        response = self.client.post(
            reset_url,
            {
                'new_password1': new_password,
                'new_password2': new_password,
            },
            follow=True,
        )

        self.assertEqual(
            response.redirect_chain,
            [(reverse('driver_login'), 302)],
        )
        self.assertContains(
            response,
            'Your password has been reset. You can now log in.',
        )
        self.driver.refresh_from_db()
        challenge.refresh_from_db()
        self.assertTrue(self.driver.check_password(new_password))
        self.assertTrue(challenge.is_used)
        self.assertNotIn('driver_password_reset_token', self.client.session)
        self.assertNotIn(
            'driver_password_reset_verified_token',
            self.client.session,
        )

        response = self.client.post(
            reverse('driver_login'),
            {'email': self.driver.email, 'password': new_password},
        )
        self.assertRedirects(response, reverse('driver_dashboard'))

    def test_reset_code_page_requires_a_valid_driver_reset_session(self):
        response = self.client.get(reverse('driver_reset_otp'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Code expired')
        self.assertContains(response, reverse('driver_forgot_password'))
        self.assertContains(response, reverse('driver_login'))


class CustomerRegistrationTests(TestCase):
    def test_registration_page_shows_required_customer_fields(self):
        response = self.client.get(reverse('user_register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create your account')
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'name="mobile"')
        self.assertContains(response, 'Phone')

    def test_customer_can_register_with_hashed_password(self):
        response = self.client.post(
            reverse('user_register'),
            {
                'name': 'Morgan Customer',
                'email': 'morgan@example.com',
                'password': 'Strong-Pass-932!',
                'mobile': '5559876543',
            },
        )

        customer = CustomerUser.objects.get(email='morgan@example.com')
        self.assertRedirects(response, reverse('user_register'))
        self.assertEqual(customer.name, 'Morgan Customer')
        self.assertEqual(customer.mobile, '5559876543')
        self.assertNotEqual(customer.password, 'Strong-Pass-932!')
        self.assertTrue(customer.check_password('Strong-Pass-932!'))

    def test_customer_registration_rejects_duplicate_email_and_short_password(self):
        CustomerUser.objects.create(
            name='Existing Customer',
            email='existing@example.com',
            mobile='5551234567',
            password='existing-password',
        )

        for password in ('Strong-Pass-932!', 'short'):
            with self.subTest(password=password):
                response = self.client.post(
                    reverse('user_register'),
                    {
                        'name': 'New Customer',
                        'email': 'existing@example.com',
                        'password': password,
                        'mobile': '5557654321',
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(CustomerUser.objects.count(), 1)
                if password == 'short':
                    self.assertContains(response, 'at least 8 characters')
                else:
                    self.assertContains(response, 'already exists')

    def test_customer_registration_rejects_invalid_phone_and_weak_password(self):
        invalid_submissions = (
            ('555-abc-1234', 'Strong-Pass-932!'),
            ('1234567890', 'password'),
            ('1234567890', '12345678'),
        )

        for index, (mobile, password) in enumerate(invalid_submissions):
            with self.subTest(mobile=mobile, password=password):
                response = self.client.post(
                    reverse('user_register'),
                    {
                        'name': 'New Customer',
                        'email': f'customer-{index}@example.com',
                        'password': password,
                        'mobile': mobile,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(CustomerUser.objects.count(), 0)

    def test_customer_registration_normalizes_email_and_accepts_formatted_phone(self):
        response = self.client.post(
            reverse('user_register'),
            {
                'name': 'Morgan Customer',
                'email': '  MORGAN@example.com ',
                'password': 'Strong-Pass-932!',
                'mobile': '+1 (555) 987-6543',
            },
        )

        customer = CustomerUser.objects.get()
        self.assertRedirects(response, reverse('user_register'))
        self.assertEqual(customer.email, 'morgan@example.com')
        self.assertEqual(customer.mobile, '+15559876543')


class CustomerLoginTests(TestCase):
    def setUp(self):
        self.customer = CustomerUser.objects.create(
            name='Morgan Customer',
            email='morgan@example.com',
            mobile='5559876543',
            password='Strong-Pass-932!',
        )

    def test_login_page_shows_email_and_password_fields(self):
        response = self.client.get(reverse('user_login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign in to your account')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, reverse('user_register'))

    def test_customer_can_sign_in_with_email_and_password(self):
        response = self.client.post(
            reverse('user_login'),
            {'email': 'MORGAN@example.com', 'password': 'Strong-Pass-932!'},
        )

        self.assertRedirects(response, reverse('user_dashboard'))
        self.assertEqual(
            self.client.session['customer_user_id'],
            self.customer.pk,
        )
        response = self.client.get(reverse('user_dashboard'))
        self.assertContains(response, 'Welcome back, Morgan Customer')
        self.assertContains(response, 'morgan@example.com')
        self.assertContains(response, 'Sign out')

    def test_customer_login_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse('user_login'),
            {'email': 'morgan@example.com', 'password': 'incorrect-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid email or password.')
        self.assertNotIn('customer_user_id', self.client.session)

    def test_customer_can_sign_out(self):
        self.client.force_login(
            get_user_model().objects.create_user(
                username='admin',
                password='admin-password',
                is_staff=True,
            )
        )
        self.client.session['customer_user_id'] = self.customer.pk
        self.client.session.save()

        response = self.client.post(reverse('user_logout'), follow=True)

        self.assertRedirects(
            response,
            reverse('user_login'),
            status_code=302,
        )
        self.assertNotIn('customer_user_id', self.client.session)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, 'signed out')

    def test_customer_logout_rejects_get_requests(self):
        response = self.client.get(reverse('user_logout'))

        self.assertEqual(response.status_code, 405)

    def test_customer_dashboard_requires_a_valid_customer_session(self):
        response = self.client.get(reverse('user_dashboard'))
        self.assertRedirects(response, reverse('user_login'))

        session = self.client.session
        session['customer_user_id'] = self.customer.pk
        session.save()
        response = self.client.get(reverse('user_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Morgan Customer')
        self.assertContains(response, '5559876543')

    def test_login_page_redirects_signed_in_customer_to_dashboard(self):
        session = self.client.session
        session['customer_user_id'] = self.customer.pk
        session.save()

        response = self.client.get(reverse('user_login'))

        self.assertRedirects(response, reverse('user_dashboard'))


class CustomerTaxiBookingTests(TestCase):
    def setUp(self):
        self.customer = CustomerUser.objects.create(
            name='Morgan Customer',
            email='morgan@example.com',
            mobile='5559876543',
            password='Strong-Pass-932!',
        )
        self.driver = Driver.objects.create(
            name='Morgan Driver',
            email='driver@example.com',
            license_number='DL-123456',
            mobile='5551234567',
            password='driver-password',
        )
        self.taxi = Taxi.objects.create(
            number='CAB-123',
            type='Sedan',
            source='Downtown',
            destination='Airport',
            price='25.50',
            driver=self.driver,
        )
        session = self.client.session
        session['customer_user_id'] = self.customer.pk
        session.save()

    def test_taxi_detail_offers_booking_when_taxi_is_available(self):
        response = self.client.get(
            reverse('user_taxi_detail', args=[self.taxi.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirm Booking')
        self.assertContains(
            response,
            f'action="{reverse("book_taxi", args=[self.taxi.pk])}"',
        )

    def test_taxi_detail_does_not_offer_booking_when_taxi_is_unavailable(self):
        self.taxi.availability = False
        self.taxi.save(update_fields=['availability'])

        response = self.client.get(
            reverse('user_taxi_detail', args=[self.taxi.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Taxi unavailable')
        self.assertNotContains(response, 'Confirm Booking')

    def test_customer_can_confirm_booking_from_taxi_detail(self):
        response = self.client.post(
            reverse('book_taxi', args=[self.taxi.pk]),
            follow=True,
        )

        booking = Booking.objects.get()
        self.assertRedirects(
            response,
            reverse('booking_confirmation', args=[booking.pk]),
        )
        self.assertEqual(booking.user, self.customer)
        self.assertEqual(booking.taxi, self.taxi)
        self.assertEqual(booking.status, 'Pending')
        self.taxi.refresh_from_db()
        self.assertFalse(self.taxi.availability)
        self.assertContains(response, 'Booking confirmed')
        self.assertContains(response, 'Pending')
        self.assertContains(response, 'Sedan')
        self.assertContains(response, 'CAB-123')
        self.assertContains(response, 'Morgan Driver')
        self.assertContains(response, 'driver@example.com')
        self.assertContains(response, '5551234567')

    def test_customer_booking_history_shows_taxi_and_driver_details(self):
        Booking.objects.create(
            user=self.customer,
            taxi=self.taxi,
            status='Approved',
        )

        response = self.client.get(reverse('booking_history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sedan')
        self.assertContains(response, 'CAB-123')
        self.assertContains(response, '25.50')
        self.assertContains(response, 'Morgan Driver')
        self.assertContains(response, 'driver@example.com')
        self.assertContains(response, '5551234567')

    def test_customer_cannot_view_another_customers_booking_confirmation(self):
        another_customer = CustomerUser.objects.create(
            name='Another Customer',
            email='another@example.com',
            mobile='5557654321',
            password='Strong-Pass-932!',
        )
        booking = Booking.objects.create(
            user=another_customer,
            taxi=self.taxi,
            status='Pending',
        )

        response = self.client.get(
            reverse('booking_confirmation', args=[booking.pk]),
        )
        self.assertEqual(response.status_code, 404)

    def test_customer_can_cancel_own_booking(self):
        booking = Booking.objects.create(
            user=self.customer,
            taxi=self.taxi,
            status='Pending',
        )
        self.taxi.availability = False
        self.taxi.save(update_fields=['availability'])

        response = self.client.post(
            reverse('cancel_booking', args=[booking.pk]),
        )

        self.assertRedirects(response, reverse('booking_history'))
        booking.refresh_from_db()
        self.taxi.refresh_from_db()
        self.assertEqual(booking.status, 'Cancelled')
        self.assertTrue(self.taxi.availability)

    def test_customer_cannot_cancel_another_customers_booking(self):
        another_customer = CustomerUser.objects.create(
            name='Another Customer',
            email='another@example.com',
            mobile='5557654321',
            password='Strong-Pass-932!',
        )
        booking = Booking.objects.create(
            user=another_customer,
            taxi=self.taxi,
            status='Pending',
        )

        response = self.client.post(
            reverse('cancel_booking', args=[booking.pk]),
        )

        self.assertEqual(response.status_code, 404)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'Pending')


class CustomerForgotPasswordFormTests(TestCase):
    def setUp(self):
        self.customer = CustomerUser.objects.create(
            name='Morgan Customer',
            email='morgan@example.com',
            mobile='5559876543',
            password='Strong-Pass-932!',
        )

    def test_forgot_password_page_has_email_field_and_back_link(self):
        response = self.client.get(reverse('user_forgot_password'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Forgot your password?')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, reverse('user_login'))

    def test_reset_code_page_requires_a_valid_reset_session(self):
        response = self.client.get(reverse('user_reset_otp'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Code expired')
        self.assertContains(response, reverse('user_forgot_password'))

    def test_forgot_password_form_validates_email(self):
        response = self.client.post(
            reverse('user_forgot_password'),
            {'email': 'not-an-email'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid email address')
        self.assertNotContains(response, 'Your email was accepted')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_valid_forgot_password_email_sends_hashed_otp(self):
        response = self.client.post(
            reverse('user_forgot_password'),
            {'email': 'MORGAN@example.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'check the')
        self.assertContains(response, reverse('user_reset_otp'))
        challenge = CustomerPasswordResetOTP.objects.get(user=self.customer)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['morgan@example.com'])
        self.assertIn('reset code is', mail.outbox[0].body)
        otp = re.search(r'code is (\d{6})', mail.outbox[0].body).group(1)
        self.assertNotEqual(challenge.otp_hash, otp)
        self.assertTrue(check_password(otp, challenge.otp_hash))
        self.assertLessEqual(challenge.created_at, timezone.now())
        self.assertGreater(challenge.expires_at, timezone.now())
        self.assertGreaterEqual(
            challenge.expires_at - challenge.created_at,
            timedelta(minutes=9, seconds=59),
        )
        self.assertLessEqual(
            challenge.expires_at - challenge.created_at,
            timedelta(minutes=10),
        )
        self.assertEqual(
            self.client.session['customer_password_reset_token'],
            str(challenge.token),
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_requesting_new_otp_replaces_previous_temporary_code(self):
        old_challenge = CustomerPasswordResetOTP.objects.create(
            user=self.customer,
            otp_hash=make_password('123456'),
            expires_at=timezone.now() + timedelta(minutes=10),
            is_used=True,
        )

        self.client.post(
            reverse('user_forgot_password'),
            {'email': self.customer.email},
        )

        challenges = CustomerPasswordResetOTP.objects.filter(user=self.customer)
        self.assertEqual(challenges.count(), 1)
        self.assertNotEqual(challenges.get().pk, old_challenge.pk)

    def test_valid_email_without_matching_account_keeps_generic_response(self):
        response = self.client.post(
            reverse('user_forgot_password'),
            {'email': 'unknown@example.com'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'If an account matches')
        self.assertEqual(CustomerPasswordResetOTP.objects.count(), 0)
        self.assertNotIn(
            'customer_password_reset_token',
            self.client.session,
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    )
    def test_forgot_password_otp_is_sent_to_console_backend(self):
        with captured_stdout() as output:
            response = self.client.post(
                reverse('user_forgot_password'),
                {'email': self.customer.email},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('From: admin@taxibooking.local', output.getvalue())
        self.assertIn('To: morgan@example.com', output.getvalue())
        self.assertRegex(output.getvalue(), r'reset code is \d{6}')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_customer_can_verify_otp_and_set_a_new_password(self):
        self.client.post(
            reverse('user_forgot_password'),
            {'email': self.customer.email},
        )
        challenge = CustomerPasswordResetOTP.objects.get(user=self.customer)
        otp = re.search(r'code is (\d{6})', mail.outbox[0].body).group(1)
        url = reverse('user_reset_otp')

        response = self.client.post(url, {'otp': otp})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your verification code has been confirmed.')
        self.assertContains(response, 'name="new_password1"')

        response = self.client.post(
            url,
            {
                'new_password1': 'New-Customer-Password-723!',
                'new_password2': 'New-Customer-Password-723!',
            },
            follow=True,
        )

        self.assertEqual(
            response.redirect_chain,
            [(reverse('user_login'), 302)],
        )
        self.assertContains(
            response,
            'Your password has been reset. You can now log in.',
        )
        self.customer.refresh_from_db()
        challenge.refresh_from_db()
        self.assertTrue(self.customer.check_password('New-Customer-Password-723!'))
        self.assertTrue(challenge.is_used)
        self.assertNotIn('customer_password_reset_token', self.client.session)
        self.assertNotIn(
            'customer_password_reset_verified_token',
            self.client.session,
        )
        response = self.client.post(
            reverse('user_login'),
            {
                'email': self.customer.email,
                'password': 'New-Customer-Password-723!',
            },
        )
        self.assertRedirects(response, reverse('user_dashboard'))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_customer_cannot_change_password_before_otp_verification(self):
        self.client.post(
            reverse('user_forgot_password'),
            {'email': self.customer.email},
        )

        response = self.client.post(
            reverse('user_reset_otp'),
            {
                'new_password1': 'New-Customer-Password-723!',
                'new_password2': 'New-Customer-Password-723!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password('Strong-Pass-932!'))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_customer_reset_rejects_invalid_otp_after_five_attempts(self):
        self.client.post(
            reverse('user_forgot_password'),
            {'email': self.customer.email},
        )
        challenge = CustomerPasswordResetOTP.objects.get(user=self.customer)
        url = reverse('user_reset_otp')

        for _ in range(5):
            response = self.client.post(url, {'otp': '000000'})

        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 5)
        self.assertContains(response, 'Too many attempts')
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password('Strong-Pass-932!'))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_expired_customer_reset_code_cannot_be_used(self):
        self.client.post(
            reverse('user_forgot_password'),
            {'email': self.customer.email},
        )
        challenge = CustomerPasswordResetOTP.objects.get(user=self.customer)
        challenge.expires_at = timezone.now() - timedelta(seconds=1)
        challenge.save(update_fields=['expires_at'])

        response = self.client.post(
            reverse('user_reset_otp'),
            {'otp': '123456'},
        )

        self.assertContains(response, 'Code expired')
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password('Strong-Pass-932!'))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminAuthenticationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username='admin',
            password='admin-password',
            email='admin@example.com',
            is_staff=True,
        )
        self.customer = user_model.objects.create_user(
            username='customer',
            password='customer-password',
        )

    def test_admin_can_log_in_and_view_dashboard(self):
        response = self.client.post(
            reverse('admin_login'),
            {'username': 'admin', 'password': 'admin-password'},
        )

        self.assertRedirects(response, reverse('admin_dashboard'))
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Taxi Admin')
        self.assertContains(response, 'Drivers')
        self.assertContains(response, 'Users')
        self.assertContains(response, 'Bookings')
        self.assertContains(response, 'Manage Drivers')
        self.assertContains(response, 'Manage Users')
        self.assertContains(response, 'Manage Bookings')
        self.assertContains(response, 'navbar-expand-lg')
        self.assertContains(response, 'data-bs-target="#adminNavbar"')
        self.assertContains(response, 'core/images/admin-profile.jpg')
        self.assertContains(response, 'Administrator')
        self.assertContains(response, 'Active')
        self.assertContains(response, 'action="/logout/"')
        self.assertNotContains(response, 'href="#drivers"')
        self.assertNotContains(response, 'href="#users"')
        self.assertNotContains(response, 'href="#bookings"')

    def test_dashboard_shows_customer_driver_and_admin_counts(self):
        self.client.force_login(self.admin)
        CustomerUser.objects.create(
            name='Morgan Customer',
            email='morgan@example.com',
            mobile='5559876543',
            password='customer-password',
        )
        Driver.objects.create(
            name='Taylor Driver',
            email='taylor@example.com',
            license_number='DL-123456',
            mobile='5551234567',
            password='driver-password',
        )

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_customers'], 1)
        self.assertEqual(response.context['total_drivers'], 1)
        self.assertEqual(response.context['total_admins'], 1)
        self.assertContains(response, 'Registered customers')
        self.assertContains(response, 'Registered drivers')
        self.assertContains(response, 'Administrator accounts')

    def test_admin_can_view_registered_drivers(self):
        self.client.force_login(self.admin)
        Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='driver-password',
        )
        Driver.objects.create(
            name='Taylor Driver',
            email='taylor@example.com',
            license_number='DL-654321',
            mobile='5551234567',
            password='another-driver-password',
        )

        response = self.client.get(reverse('admin_drivers'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registered drivers')
        self.assertContains(response, 'Morgan Driver')
        self.assertContains(response, 'morgan@example.com')
        self.assertContains(response, 'DL-123456')
        self.assertContains(response, '5559876543')
        self.assertContains(response, 'Taylor Driver')
        self.assertContains(response, 'taylor@example.com')
        self.assertContains(response, 'DL-654321')
        self.assertContains(response, '5551234567')
        self.assertNotContains(response, 'driver-password')
        self.assertNotContains(response, 'another-driver-password')
        self.assertContains(response, 'Search drivers')
        self.assertContains(response, 'Delete')
        dashboard = self.client.get(reverse('admin_dashboard'))
        self.assertContains(
            dashboard,
            f'href="{reverse("admin_drivers")}"',
        )
        self.assertNotContains(dashboard, 'Morgan Driver')

    def test_admin_can_search_drivers_by_name_email_license_or_mobile(self):
        self.client.force_login(self.admin)
        Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='driver-password',
        )
        Driver.objects.create(
            name='Taylor Driver',
            email='taylor@example.com',
            license_number='DL-654321',
            mobile='5551234567',
            password='another-driver-password',
        )

        for query in ('Morgan', 'taylor@example.com', 'DL-123456', '5551234567'):
            with self.subTest(query=query):
                response = self.client.get(
                    reverse('admin_drivers'),
                    {'q': query},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '1 driver')
                expected_name = (
                    'Morgan Driver'
                    if query in ('Morgan', 'DL-123456')
                    else 'Taylor Driver'
                )
                excluded_name = (
                    'Taylor Driver'
                    if expected_name == 'Morgan Driver'
                    else 'Morgan Driver'
                )
                self.assertContains(response, expected_name)
                self.assertNotContains(response, excluded_name)

        response = self.client.get(
            reverse('admin_drivers'),
            {'q': 'no-such-driver'},
        )
        self.assertContains(response, 'No drivers match your search')

    def test_admin_can_delete_driver_with_post_only(self):
        self.client.force_login(self.admin)
        driver = Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='driver-password',
        )
        delete_url = reverse('admin_driver_delete', args=[driver.pk])

        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Driver.objects.filter(pk=driver.pk).exists())

        response = self.client.post(delete_url, follow=True)

        self.assertRedirects(
            response,
            reverse('admin_drivers'),
            fetch_redirect_response=False,
        )
        self.assertFalse(Driver.objects.filter(pk=driver.pk).exists())
        self.assertContains(response, 'Driver deleted successfully.')

    def test_driver_delete_requires_staff_authentication(self):
        response = self.client.post(
            reverse('admin_driver_delete', args=[1]),
        )

        self.assertRedirects(
            response,
            f"{reverse('admin_login')}?next=/drivers/1/delete/",
        )

    def test_driver_list_requires_staff_authentication(self):
        response = self.client.get(reverse('admin_drivers'))

        self.assertRedirects(
            response,
            f"{reverse('admin_login')}?next={reverse('admin_drivers')}",
        )

    def test_admin_can_view_driver_profile_and_empty_booking_history(self):
        self.client.force_login(self.admin)
        driver = Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='driver-password',
        )

        response = self.client.get(
            reverse('admin_driver_detail', args=[driver.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Driver profile')
        self.assertContains(response, 'Morgan Driver')
        self.assertContains(response, 'morgan@example.com')
        self.assertContains(response, 'DL-123456')
        self.assertContains(response, '5559876543')
        self.assertContains(response, 'Booking history')
        self.assertContains(response, 'No bookings yet')
        self.assertNotContains(response, 'driver-password')

    def test_driver_profile_returns_404_for_unknown_driver(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('admin_driver_detail', args=[99999]),
        )

        self.assertEqual(response.status_code, 404)

    def test_driver_profile_requires_staff_authentication(self):
        response = self.client.get(
            reverse('admin_driver_detail', args=[1]),
        )

        self.assertRedirects(
            response,
            f"{reverse('admin_login')}?next=/drivers/1/",
        )

    def test_non_staff_user_cannot_log_in(self):
        response = self.client.post(
            reverse('admin_login'),
            {'username': 'customer', 'password': 'customer-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Invalid credentials or you are not authorized as an admin.',
        )
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_invalid_password_does_not_log_in(self):
        response = self.client.post(
            reverse('admin_login'),
            {'username': 'admin', 'password': 'wrong-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_dashboard_requires_staff_authentication(self):
        response = self.client.get(reverse('admin_dashboard'))

        self.assertRedirects(
            response,
            f"{reverse('admin_login')}?next={reverse('admin_dashboard')}",
        )

    def test_admin_can_view_registered_users(self):
        self.client.force_login(self.admin)
        CustomerUser.objects.create(
            name='Rider One',
            email='rider@example.com',
            mobile='5551234567',
            password='rider-password',
        )

        response = self.client.get(reverse('admin_users'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registered users')
        self.assertContains(response, 'Rider One')
        self.assertContains(response, 'rider@example.com')
        self.assertContains(response, 'Edit')
        self.assertContains(response, 'Delete')

    def test_admin_can_search_users_by_name_or_email(self):
        self.client.force_login(self.admin)
        matching_name = CustomerUser.objects.create(
            name='Alice Rider',
            email='alice@example.com',
            mobile='5551234567',
            password='rider-password',
        )
        matching_email = CustomerUser.objects.create(
            name='Bob Rider',
            email='contact@example.com',
            mobile='5557654321',
            password='rider-password',
        )
        CustomerUser.objects.create(
            name='Charlie Rider',
            email='charlie@example.com',
            mobile='5551112222',
            password='rider-password',
        )

        by_name = self.client.get(reverse('admin_users'), {'q': 'alice'})
        self.assertEqual(list(by_name.context['users']), [matching_name])
        self.assertContains(by_name, 'Alice Rider')
        self.assertNotContains(by_name, 'Bob Rider')
        self.assertContains(by_name, 'value="alice"')

        by_email = self.client.get(reverse('admin_users'), {'q': 'CONTACT@'})
        self.assertEqual(list(by_email.context['users']), [matching_email])
        self.assertContains(by_email, 'Bob Rider')
        self.assertNotContains(by_email, 'Alice Rider')

    def test_user_search_with_no_matches_shows_empty_state(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_users'), {'q': 'missing'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No matching users')
        self.assertNotContains(response, 'No users yet')

    def test_non_staff_user_cannot_view_registered_users(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse('admin_users'))

        self.assertRedirects(
            response,
            f"{reverse('admin_login')}?next={reverse('admin_users')}",
        )

    def test_admin_can_view_user_profile_details(self):
        self.client.force_login(self.admin)
        customer = CustomerUser.objects.create(
            name='Rider One',
            email='rider@example.com',
            mobile='5551234567',
            password='rider-password',
        )

        response = self.client.get(
            reverse('admin_user_detail', args=[customer.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rider One')
        self.assertContains(response, 'rider@example.com')
        self.assertContains(response, '5551234567')
        self.assertContains(response, f'User #{customer.pk}')
        self.assertContains(
            response,
            reverse('admin_user_edit', args=[customer.pk]),
        )
        self.assertNotContains(response, customer.password)

    def test_admin_user_profile_lists_only_that_users_bookings(self):
        self.client.force_login(self.admin)
        customer = CustomerUser.objects.create(
            name='Rider One',
            email='rider@example.com',
            mobile='5551234567',
            password='rider-password',
        )
        other_customer = CustomerUser.objects.create(
            name='Rider Two',
            email='rider2@example.com',
            mobile='5557654321',
            password='rider-password',
        )
        driver = Driver.objects.create(
            name='Morgan Driver',
            email='morgan@example.com',
            license_number='DL-123456',
            mobile='5559876543',
            password='driver-password',
        )
        taxi = Taxi.objects.create(
            number='CAB-123',
            type='Sedan',
            source='Downtown',
            destination='Airport',
            price='25.50',
            availability=True,
            driver=driver,
        )
        customer_booking = Booking.objects.create(
            user=customer,
            taxi=taxi,
        )
        Booking.objects.create(
            user=other_customer,
            taxi=taxi,
        )

        response = self.client.get(
            reverse('admin_user_detail', args=[customer.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context['bookings']),
            [customer_booking],
        )
        self.assertContains(response, 'Booking history')
        self.assertContains(response, '#{}'.format(customer_booking.pk))
        self.assertContains(response, 'CAB-123')

    def test_non_staff_user_cannot_view_user_profile_details(self):
        self.client.force_login(self.customer)
        customer = CustomerUser.objects.create(
            name='Rider One',
            email='rider@example.com',
            mobile='5551234567',
            password='rider-password',
        )

        response = self.client.get(
            reverse('admin_user_detail', args=[customer.pk]),
        )

        self.assertRedirects(
            response,
            f"{reverse('admin_login')}?next="
            f"{reverse('admin_user_detail', args=[customer.pk])}",
        )

    def test_user_profile_returns_404_for_unknown_user(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('admin_user_detail', args=[99999]),
        )

        self.assertEqual(response.status_code, 404)

    def test_admin_can_edit_user_details_without_changing_password(self):
        self.client.force_login(self.admin)
        customer = CustomerUser.objects.create(
            name='Rider One',
            email='rider@example.com',
            mobile='5551234567',
            password='rider-password',
        )
        password_hash = customer.password

        response = self.client.post(
            reverse('admin_user_edit', args=[customer.pk]),
            {
                'name': 'Rider Updated',
                'email': 'updated@example.com',
                'mobile': '5557654321',
            },
        )

        self.assertRedirects(response, reverse('admin_users'))
        customer.refresh_from_db()
        self.assertEqual(customer.name, 'Rider Updated')
        self.assertEqual(customer.email, 'updated@example.com')
        self.assertEqual(customer.mobile, '5557654321')
        self.assertEqual(customer.password, password_hash)
        self.assertTrue(customer.check_password('rider-password'))

    def test_admin_can_delete_user_with_post_only(self):
        self.client.force_login(self.admin)
        customer = CustomerUser.objects.create(
            name='Rider One',
            email='rider@example.com',
            mobile='5551234567',
            password='rider-password',
        )
        delete_url = reverse('admin_user_delete', args=[customer.pk])

        response = self.client.get(delete_url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(CustomerUser.objects.filter(pk=customer.pk).exists())

        response = self.client.post(delete_url)

        self.assertRedirects(response, reverse('admin_users'))
        self.assertFalse(CustomerUser.objects.filter(pk=customer.pk).exists())

        self.client.force_login(self.customer)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertRedirects(
            response,
            f"{reverse('admin_login')}?next={reverse('admin_dashboard')}",
        )

    def test_admin_can_log_out_with_post(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin_logout'))

        self.assertRedirects(response, reverse('admin_login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_rejects_get_requests(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('admin_logout'))

        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def test_staff_admin_can_register_an_admin_account(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('admin_register'),
            {
                'username': 'new-admin',
                'password1': 'Strong-Pass-932!',
                'password2': 'Strong-Pass-932!',
            },
        )

        self.assertRedirects(response, reverse('admin_register'))
        new_admin = get_user_model().objects.get(username='new-admin')
        self.assertTrue(new_admin.is_staff)
        self.assertTrue(new_admin.check_password('Strong-Pass-932!'))
        self.assertTrue(AdminAccount.objects.filter(user=new_admin).exists())

    def test_non_staff_user_cannot_register_an_admin(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse('admin_register'))

        self.assertRedirects(
            response,
            f"{reverse('admin_login')}?next={reverse('admin_register')}",
        )
        self.assertFalse(
            get_user_model().objects.filter(username='new-admin').exists()
        )

    def test_registration_form_rejects_mismatched_passwords(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('admin_register'),
            {
                'username': 'new-admin',
                'password1': 'Strong-Pass-932!',
                'password2': 'Different-Pass-932!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            get_user_model().objects.filter(username='new-admin').exists()
        )
        self.assertContains(response, 'The two password fields didn')

    def test_password_reset_sends_a_hashed_otp_to_staff_admin(self):
        response = self.client.post(
            reverse('admin_forgot_password'),
            {'email': 'admin@example.com'},
        )

        challenge = AdminPasswordResetOTP.objects.get(user=self.admin)
        self.assertRedirects(response, reverse('admin_forgot_password_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reset code is', mail.outbox[0].body)
        otp = re.search(r'code is (\d{6})', mail.outbox[0].body).group(1)
        self.assertNotEqual(challenge.otp_hash, otp)
        self.assertGreater(challenge.expires_at, timezone.now())
        self.assertLess(challenge.expires_at, timezone.now() + timedelta(minutes=11))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend',
    )
    def test_password_reset_otp_is_printed_to_console(self):
        with captured_stdout() as output:
            response = self.client.post(
                reverse('admin_forgot_password'),
                {'email': 'admin@example.com'},
            )

        self.assertRedirects(response, reverse('admin_forgot_password_done'))
        self.assertIn('From: admin@taxibooking.local', output.getvalue())
        self.assertIn('To: admin@example.com', output.getvalue())
        self.assertRegex(output.getvalue(), r'reset code is \d{6}')

    def test_password_can_be_reset_after_otp_is_verified(self):
        self.client.post(
            reverse('admin_forgot_password'),
            {'email': 'admin@example.com'},
        )
        challenge = AdminPasswordResetOTP.objects.get(user=self.admin)
        otp = re.search(r'code is (\d{6})', mail.outbox[0].body).group(1)
        url = reverse('admin_reset_otp')

        response = self.client.post(url, {'otp': otp})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your verification code has been confirmed.')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('admin-password'))

        response = self.client.post(
            url,
            {
                'new_password1': 'New-Admin-Password-723!',
                'new_password2': 'New-Admin-Password-723!',
            },
            follow=True,
        )

        self.assertEqual(
            response.redirect_chain,
            [(reverse('admin_login'), 302)],
        )
        self.assertContains(
            response,
            'Your password has been reset. You can now log in.',
        )
        self.assertContains(response, 'alert-success')
        self.admin.refresh_from_db()
        challenge.refresh_from_db()
        self.assertTrue(self.admin.check_password('New-Admin-Password-723!'))
        self.assertTrue(challenge.is_used)

    def test_password_cannot_be_reset_before_otp_is_verified(self):
        self.client.post(
            reverse('admin_forgot_password'),
            {'email': 'admin@example.com'},
        )

        response = self.client.post(
            reverse('admin_reset_otp'),
            {
                'new_password1': 'New-Admin-Password-723!',
                'new_password2': 'New-Admin-Password-723!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('admin-password'))

    def test_invalid_otp_is_limited_to_five_attempts(self):
        self.client.post(
            reverse('admin_forgot_password'),
            {'email': 'admin@example.com'},
        )
        challenge = AdminPasswordResetOTP.objects.get(user=self.admin)
        url = reverse('admin_reset_otp')

        for _ in range(5):
            response = self.client.post(url, {'otp': '000000'})

        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 5)
        self.assertContains(response, 'Too many attempts')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('admin-password'))
