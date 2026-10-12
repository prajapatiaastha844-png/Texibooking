
import uuid

from django.conf import settings
from django.db import models
from django.contrib.auth.hashers import check_password, identify_hasher, make_password


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
    password = models.CharField(max_length=128)

    def set_password(self, raw_password):
        """Store the password as a secure hash."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Check whether the entered password matches."""
        return check_password(raw_password, self.password)

    def save(self, *args, **kwargs):
        if self.password:
            try:
                identify_hasher(self.password)
            except ValueError:
                self.set_password(self.password)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name