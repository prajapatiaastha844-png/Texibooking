
import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.hashers import check_password, identify_hasher, make_password


class Booking(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    taxi = models.ForeignKey(
        'core.Taxi',
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    date = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    def __str__(self):
        return f'{self.user.name} - {self.taxi.number}'


class AdminAccount(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_account',
    )


class AdminPasswordResetOTP(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    otp_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_otps',
    )


class CustomerPasswordResetOTP(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    otp_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    user = models.ForeignKey(
        'core.User',
        on_delete=models.CASCADE,
        related_name='password_reset_otps',
    )


class DriverPasswordResetOTP(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    otp_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    driver = models.ForeignKey(
        'core.Driver',
        on_delete=models.CASCADE,
        related_name='password_reset_otps',
    )


class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15)
    password = models.CharField(max_length=128)

    def set_password(self, raw_password):
        """Store the password as a secure hash."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Check whether the entered password matches."""
        return check_password(raw_password, self.password)

    def save(self, *args, **kwargs):
        # Hash the password if it is not already hashed.
        if self.password:
            try:
                identify_hasher(self.password)
            except ValueError:
                self.set_password(self.password)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Driver(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    license_number = models.CharField(
        max_length=50,
        unique=True
    )
    mobile = models.CharField(max_length=15)
    taxi_number = models.CharField(max_length=20, blank=True)
    password = models.CharField(max_length=128)

    def set_password(self, raw_password):
        """Store the password as a secure hash."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Check whether the entered password matches."""
        return check_password(raw_password, self.password)

    def _normalize_fields(self):
        self.name = self.name.strip()
        self.email = self.email.strip()
        self.license_number = self.license_number.strip()
        self.mobile = self.mobile.strip()

        if re.fullmatch(r'\+?[\d\s().-]+', self.mobile):
            digits = ''.join(
                character for character in self.mobile
                if character.isdigit()
            )
            if 7 <= len(digits) <= 15:
                self.mobile = f'+{digits}' if self.mobile.startswith('+') else digits

    def clean(self):
        super().clean()
        errors = {}

        self._normalize_fields()
        if not self.name:
            errors['name'] = 'Enter the driver name.'

        if not re.fullmatch(r'\+?[\d\s().-]+', self.mobile):
            errors['mobile'] = 'Enter a valid phone number.'
        else:
            digits = ''.join(
                character for character in self.mobile
                if character.isdigit()
            )
            if not 7 <= len(digits) <= 15:
                errors['mobile'] = (
                    'Phone number must contain between 7 and 15 digits.'
                )
            else:
                self.mobile = f'+{digits}' if self.mobile.startswith('+') else digits

        if self.email:
            existing_drivers = Driver.objects.filter(
                email__iexact=self.email,
            ).exclude(email=self.email)
            if self.pk:
                existing_drivers = existing_drivers.exclude(pk=self.pk)
            if existing_drivers.exists():
                errors['email'] = (
                    'A driver with this email address already exists.'
                )

        if self.license_number:
            existing_drivers = Driver.objects.filter(
                license_number__iexact=self.license_number,
            ).exclude(license_number=self.license_number)
            if self.pk:
                existing_drivers = existing_drivers.exclude(pk=self.pk)
            if existing_drivers.exists():
                errors['license_number'] = (
                    'This license number is already registered.'
                )

        self.email = self.email.lower()

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self._normalize_fields()
        self.full_clean(validate_unique=False)

        if self.password:
            try:
                identify_hasher(self.password)
            except ValueError:
                self.set_password(self.password)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Taxi(models.Model):
    number = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=50)
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    availability = models.BooleanField(default=True)
    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        related_name='taxis',
    )

    def __str__(self):
        return self.number


class TaxiDetails(models.Model):
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        related_name='taxi_details',
    )

    def __str__(self):
        return f'{self.source} to {self.destination} ({self.driver})'
