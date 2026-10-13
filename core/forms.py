import re

from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Driver, User


class CustomerRegistrationForm(forms.ModelForm):
    mobile = forms.CharField(
        label='Phone',
        max_length=32,
        widget=forms.TelInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'tel',
            'placeholder': 'Your phone number',
        }),
    )
    password = forms.CharField(
        label='Password',
        min_length=8,
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'new-password',
            'placeholder': 'At least 8 characters',
        }),
    )

    class Meta:
        model = User
        fields = ('name', 'email', 'password', 'mobile')
        labels = {'mobile': 'Phone'}
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'autocomplete': 'name',
                'placeholder': 'Your full name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control form-control-lg',
                'autocomplete': 'email',
                'placeholder': 'you@example.com',
            }),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        existing_users = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            existing_users = existing_users.exclude(pk=self.instance.pk)
        if existing_users.exists():
            raise ValidationError('A user with this email address already exists.')
        return email

    def clean_mobile(self):
        mobile = self.cleaned_data['mobile'].strip()
        if not re.fullmatch(r'\+?[\d\s().-]+', mobile):
            raise ValidationError('Enter a valid phone number.')

        digit_count = sum(character.isdigit() for character in mobile)
        if not 7 <= digit_count <= 15:
            raise ValidationError(
                'Phone number must contain between 7 and 15 digits.'
            )

        digits = ''.join(character for character in mobile if character.isdigit())
        return f'+{digits}' if mobile.startswith('+') else digits

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        if password:
            user = User(
                name=cleaned_data.get('name', ''),
                email=cleaned_data.get('email', ''),
                mobile=cleaned_data.get('mobile', ''),
            )
            try:
                validate_password(password, user=user)
            except ValidationError as error:
                self.add_error('password', error)
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class DriverRegistrationForm(forms.ModelForm):
    mobile = forms.CharField(
        label='Phone',
        max_length=32,
        widget=forms.TelInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'tel',
            'placeholder': 'Your phone number',
        }),
    )
    password = forms.CharField(
        label='Password',
        min_length=8,
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'new-password',
            'placeholder': 'At least 8 characters',
        }),
    )

    class Meta:
        model = Driver
        fields = ('name', 'email', 'license_number', 'mobile', 'password')
        labels = {'license_number': 'License number', 'mobile': 'Phone'}
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'autocomplete': 'name',
                'placeholder': 'Your full name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control form-control-lg',
                'autocomplete': 'email',
                'placeholder': 'you@example.com',
            }),
            'license_number': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'autocomplete': 'off',
                'placeholder': 'Your driver license number',
            }),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        existing_drivers = Driver.objects.filter(email__iexact=email)
        if self.instance.pk:
            existing_drivers = existing_drivers.exclude(pk=self.instance.pk)
        if existing_drivers.exists():
            raise ValidationError('A driver with this email address already exists.')
        return email

    def clean_license_number(self):
        license_number = self.cleaned_data['license_number'].strip()
        existing_drivers = Driver.objects.filter(
            license_number__iexact=license_number,
        )
        if self.instance.pk:
            existing_drivers = existing_drivers.exclude(pk=self.instance.pk)
        if existing_drivers.exists():
            raise ValidationError('This license number is already registered.')
        return license_number

    def clean_mobile(self):
        mobile = self.cleaned_data['mobile'].strip()
        if not re.fullmatch(r'\+?[\d\s().-]+', mobile):
            raise ValidationError('Enter a valid phone number.')

        digit_count = sum(character.isdigit() for character in mobile)
        if not 7 <= digit_count <= 15:
            raise ValidationError(
                'Phone number must contain between 7 and 15 digits.'
            )

        digits = ''.join(character for character in mobile if character.isdigit())
        normalized_mobile = f'+{digits}' if mobile.startswith('+') else digits
        if len(normalized_mobile) > 15:
            raise ValidationError('Phone number must be no more than 15 characters.')
        return normalized_mobile

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        if password:
            driver = Driver(
                name=cleaned_data.get('name', ''),
                email=cleaned_data.get('email', ''),
                license_number=cleaned_data.get('license_number', ''),
                mobile=cleaned_data.get('mobile', ''),
            )
            try:
                validate_password(password, user=driver)
            except ValidationError as error:
                self.add_error('password', error)
        return cleaned_data

    def save(self, commit=True):
        driver = super().save(commit=False)
        driver.set_password(self.cleaned_data['password'])
        if commit:
            driver.save()
        return driver


class CustomerLoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'email',
            'placeholder': 'you@example.com',
        }),
    )
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'current-password',
            'placeholder': 'Enter your password',
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if email and password:
            user = User.objects.filter(email__iexact=email.strip()).first()
            if user is None or not user.check_password(password):
                raise ValidationError('Invalid email or password.')
            self.customer = user
        return cleaned_data


class DriverLoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'email',
            'placeholder': 'Enter your driver account email',
        }),
    )
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'current-password',
            'placeholder': 'Enter your password',
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if email and password:
            driver = Driver.objects.filter(email__iexact=email.strip()).first()
            if driver is None or not driver.check_password(password):
                raise ValidationError('Invalid email or password.')
            self.driver = driver
        return cleaned_data


class CustomerForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label='Email address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'autocomplete': 'email',
            'placeholder': 'you@example.com',
        }),
    )


class AdminRegistrationForm(UserCreationForm):
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('name', 'email', 'mobile')


class UserSearchForm(forms.Form):
    q = forms.CharField(
        label='Search users',
        required=False,
        strip=True,
        widget=forms.SearchInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name or email',
            'aria-describedby': 'user-search-help',
        }),
    )


class DriverSearchForm(forms.Form):
    q = forms.CharField(
        label='Search drivers',
        required=False,
        strip=True,
        widget=forms.SearchInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, email, license number, or mobile',
            'aria-describedby': 'driver-search-help',
        }),
    )
