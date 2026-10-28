
import secrets
import uuid
from datetime import timedelta

from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.forms import SetPasswordForm
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.core.mail import send_mail
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import (
    AdminRegistrationForm,
    CustomerForgotPasswordForm,
    CustomerLoginForm,
    CustomerRegistrationForm,
    CustomerTaxiSearchForm,
    DriverForgotPasswordForm,
    DriverLoginForm,
    DriverRegistrationForm,
    DriverSearchForm,
    TaxiSearchForm,
    UserEditForm,
    UserSearchForm,
    TaxiForm,
)
from .models import (
    AdminAccount,
    AdminPasswordResetOTP,
    Booking,
    CustomerPasswordResetOTP,
    Driver,
    DriverPasswordResetOTP,
    User,
    Taxi,
)


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None and user.is_staff:
            login(request, user)
            return redirect('admin_dashboard')

        messages.error(
            request,
            'Invalid credentials or you are not authorized as an admin.'
        )

    return render(request, 'core/admin_login.html')


def user_register(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your account has been created successfully.')
            return redirect('user_register')
    else:
        form = CustomerRegistrationForm()

    return render(request, 'core/user_register.html', {'form': form})


def driver_register(request):
    if request.method == 'POST':
        form = DriverRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Your driver account has been created successfully.',
            )
            return redirect('driver_register')
    else:
        form = DriverRegistrationForm()

    return render(request, 'core/driver_register.html', {'form': form})


def driver_login(request):
    driver_id = request.session.get('driver_user_id')
    if driver_id is not None:
        driver = Driver.objects.filter(pk=driver_id).first()
        if driver is not None:
            return redirect('driver_dashboard')
        request.session.pop('driver_user_id', None)

    if request.method == 'POST':
        form = DriverLoginForm(request.POST)
        if form.is_valid():
            driver = form.driver
            request.session.cycle_key()
            request.session['driver_user_id'] = driver.pk
            messages.success(
                request,
                f'Welcome back, {driver.name}. You are signed in.',
            )
            return redirect('driver_dashboard')
    else:
        form = DriverLoginForm()

    return render(request, 'core/driver_login.html', {'form': form})


def user_login(request):
    customer_id = request.session.get('customer_user_id')
    if customer_id is not None:
        customer = User.objects.filter(pk=customer_id).first()
        if customer is not None:
            return redirect('user_dashboard')
        request.session.pop('customer_user_id', None)

    if request.method == 'POST':
        form = CustomerLoginForm(request.POST)
        if form.is_valid():
            customer = form.customer
            request.session.cycle_key()
            request.session['customer_user_id'] = customer.pk
            messages.success(
                request,
                f'Welcome back, {customer.name}. You are signed in.',
            )
            return redirect('user_dashboard')
    else:
        form = CustomerLoginForm()

    return render(request, 'core/user_login.html', {'form': form})


def driver_forgot_password(request):
    submitted = False
    if request.method == 'POST':
        request.session.pop('driver_password_reset_token', None)
        request.session.pop('driver_password_reset_verified_token', None)
        form = DriverForgotPasswordForm(request.POST)
        if form.is_valid():
            submitted = True
            email = form.cleaned_data['email'].strip()
            driver = Driver.objects.filter(email__iexact=email).first()
            if driver is not None:
                otp = f'{secrets.randbelow(1_000_000):06d}'

                with transaction.atomic():
                    DriverPasswordResetOTP.objects.filter(
                        driver=driver,
                    ).delete()
                    challenge = DriverPasswordResetOTP.objects.create(
                        driver=driver,
                        otp_hash=make_password(otp),
                        expires_at=timezone.now() + timedelta(minutes=10),
                    )
                    send_mail(
                        subject='Taxi Booking driver password reset',
                        message=(
                            f'Your password reset code is {otp}. '
                            'It expires in 10 minutes. If you did not request '
                            'this code, you can ignore this email.'
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[driver.email],
                        fail_silently=False,
                    )
                request.session['driver_password_reset_token'] = str(
                    challenge.token
                )
    else:
        form = DriverForgotPasswordForm()

    return render(
        request,
        'core/driver_forgot_password.html',
        {'form': form, 'submitted': submitted},
    )


def _render_driver_reset_otp(request, **context):
    return render(
        request,
        'core/user_reset_otp.html',
        {'driver_mode': True, **context},
    )


def driver_reset_otp(request):
    token = request.session.get('driver_password_reset_token')
    if not token:
        return _render_driver_reset_otp(request, expired=True)

    try:
        challenge = DriverPasswordResetOTP.objects.select_related(
            'driver',
        ).get(token=uuid.UUID(token))
    except (DriverPasswordResetOTP.DoesNotExist, ValueError):
        request.session.pop('driver_password_reset_token', None)
        request.session.pop('driver_password_reset_verified_token', None)
        return _render_driver_reset_otp(request, expired=True)

    if challenge.is_used or challenge.expires_at <= timezone.now():
        request.session.pop('driver_password_reset_token', None)
        request.session.pop('driver_password_reset_verified_token', None)
        return _render_driver_reset_otp(request, expired=True)

    if challenge.attempts >= 5:
        return _render_driver_reset_otp(request, locked=True)

    verified = (
        request.session.get('driver_password_reset_verified_token') == token
    )
    form = SetPasswordForm(
        challenge.driver,
        request.POST if request.method == 'POST' and verified else None,
    ) if verified else None
    error = None
    if request.method == 'POST':
        if not verified:
            otp = request.POST.get('otp', '').strip()
            if len(otp) != 6 or not otp.isdigit() or not check_password(
                otp,
                challenge.otp_hash,
            ):
                challenge.attempts += 1
                challenge.save(update_fields=['attempts'])
                error = 'The verification code is invalid.'
                if challenge.attempts >= 5:
                    return _render_driver_reset_otp(request, locked=True)
            else:
                request.session[
                    'driver_password_reset_verified_token'
                ] = token
                verified = True
                form = SetPasswordForm(challenge.driver)
        elif form.is_valid():
            with transaction.atomic():
                form.save()
                challenge.is_used = True
                challenge.save(update_fields=['is_used'])
            request.session.pop('driver_password_reset_token', None)
            request.session.pop('driver_password_reset_verified_token', None)
            messages.success(
                request,
                'Your password has been reset. You can now log in.',
            )
            return redirect('driver_login')

    return _render_driver_reset_otp(
        request,
        form=form,
        error=error,
        verified=verified,
    )


def user_forgot_password(request):
    submitted = False
    if request.method == 'POST':
        request.session.pop('customer_password_reset_token', None)
        request.session.pop('customer_password_reset_verified_token', None)
        form = CustomerForgotPasswordForm(request.POST)
        if form.is_valid():
            submitted = True
            email = form.cleaned_data['email'].strip()
            customer = User.objects.filter(email__iexact=email).first()
            if customer is not None:
                otp = f'{secrets.randbelow(1_000_000):06d}'

                with transaction.atomic():
                    CustomerPasswordResetOTP.objects.filter(
                        user=customer,
                    ).delete()
                    challenge = CustomerPasswordResetOTP.objects.create(
                        user=customer,
                        otp_hash=make_password(otp),
                        expires_at=timezone.now() + timedelta(minutes=10),
                    )
                    send_mail(
                        subject='Taxi Booking password reset',
                        message=(
                            f'Your password reset code is {otp}. '
                            'It expires in 10 minutes. If you did not request '
                            'this code, you can ignore this email.'
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[customer.email],
                        fail_silently=False,
                    )
                request.session['customer_password_reset_token'] = str(
                    challenge.token
                )
    else:
        form = CustomerForgotPasswordForm()

    return render(
        request,
        'core/user_forgot_password.html',
        {'form': form, 'submitted': submitted},
    )


def user_reset_otp(request):
    token = request.session.get('customer_password_reset_token')
    if not token:
        return render(
            request,
            'core/user_reset_otp.html',
            {'expired': True},
        )

    try:
        challenge = CustomerPasswordResetOTP.objects.select_related('user').get(
            token=uuid.UUID(token),
        )
    except (CustomerPasswordResetOTP.DoesNotExist, ValueError):
        request.session.pop('customer_password_reset_token', None)
        request.session.pop('customer_password_reset_verified_token', None)
        return render(
            request,
            'core/user_reset_otp.html',
            {'expired': True},
        )

    if challenge.is_used or challenge.expires_at <= timezone.now():
        request.session.pop('customer_password_reset_token', None)
        request.session.pop('customer_password_reset_verified_token', None)
        return render(
            request,
            'core/user_reset_otp.html',
            {'expired': True},
        )

    if challenge.attempts >= 5:
        return render(
            request,
            'core/user_reset_otp.html',
            {'locked': True},
        )

    verified = (
        request.session.get('customer_password_reset_verified_token') == token
    )
    form = SetPasswordForm(
        challenge.user,
        request.POST if request.method == 'POST' and verified else None,
    ) if verified else None
    error = None
    if request.method == 'POST':
        if not verified:
            otp = request.POST.get('otp', '').strip()
            if len(otp) != 6 or not otp.isdigit() or not check_password(
                otp,
                challenge.otp_hash,
            ):
                challenge.attempts += 1
                challenge.save(update_fields=['attempts'])
                error = 'The verification code is invalid.'
                if challenge.attempts >= 5:
                    return render(
                        request,
                        'core/user_reset_otp.html',
                        {'locked': True},
                    )
            else:
                request.session[
                    'customer_password_reset_verified_token'
                ] = token
                verified = True
                form = SetPasswordForm(challenge.user)
        elif form.is_valid():
            with transaction.atomic():
                form.save()
                challenge.is_used = True
                challenge.save(update_fields=['is_used'])
            request.session.pop('customer_password_reset_token', None)
            request.session.pop('customer_password_reset_verified_token', None)
            messages.success(
                request,
                'Your password has been reset. You can now log in.',
            )
            return redirect('user_login')

    return render(
        request,
        'core/user_reset_otp.html',
        {'form': form, 'error': error, 'verified': verified},
    )


def user_dashboard(request):
    customer_id = request.session.get('customer_user_id')
    if customer_id is None:
        return redirect('user_login')

    customer = User.objects.filter(pk=customer_id).first()
    if customer is None:
        request.session.pop('customer_user_id', None)
        messages.info(request, 'Please sign in to continue.')
        return redirect('user_login')

    search_form = CustomerTaxiSearchForm(request.GET or None)
    taxis = Taxi.objects.none()
    searched = bool(request.GET)
    if searched and search_form.is_valid():
        taxis = Taxi.objects.filter(
            availability=True,
            source__iexact=search_form.cleaned_data['source'],
            destination__iexact=search_form.cleaned_data['destination'],
        ).select_related('driver').order_by('price', 'number')

    return render(request, 'core/user_dashboard.html', {
        'customer': customer,
        'search_form': search_form,
        'taxis': taxis,
        'searched': searched,
    })


def user_taxi_detail(request, taxi_id):
    customer_id = request.session.get('customer_user_id')
    if customer_id is None:
        return redirect('user_login')

    customer = User.objects.filter(pk=customer_id).first()
    if customer is None:
        request.session.pop('customer_user_id', None)
        messages.info(request, 'Please sign in to continue.')
        return redirect('user_login')

    taxi = get_object_or_404(
        Taxi.objects.select_related('driver'),
        pk=taxi_id,
    )
    return render(request, 'core/user_taxi_detail.html', {
        'customer': customer,
        'taxi': taxi,
    })
    
    
@require_POST
def book_taxi(request, taxi_id):
    customer_id = request.session.get('customer_user_id')

    if customer_id is None:
        messages.info(request, 'Please sign in to book a taxi.')
        return redirect('user_login')

    customer = User.objects.filter(pk=customer_id).first()

    if customer is None:
        request.session.pop('customer_user_id', None)
        messages.info(request, 'Please sign in again.')
        return redirect('user_login')

    taxi = get_object_or_404(Taxi, pk=taxi_id)

    if not taxi.availability:
        messages.error(request, 'Sorry, this taxi is no longer available.')
        return redirect('user_dashboard')

    booking = Booking.objects.create(
        user=customer,
        taxi=taxi,
        status='Pending',
    )

    taxi.availability = False
    taxi.save(update_fields=['availability'])

    return redirect('booking_confirmation', booking_id=booking.pk)


def booking_history(request):
    customer_id = request.session.get('customer_user_id')
    if customer_id is None:
        messages.info(request, 'Please sign in to view your booking history.')
        return redirect('user_login')

    customer = User.objects.filter(pk=customer_id).first()
    if customer is None:
        request.session.pop('customer_user_id', None)
        messages.info(request, 'Please sign in again.')
        return redirect('user_login')

    bookings = Booking.objects.filter(user=customer).select_related(
        'taxi',
        'taxi__driver',
    ).order_by('-date')

    return render(request, 'core/booking_history.html', {
        'customer': customer,
        'bookings': bookings,
    })


def booking_confirmation(request, booking_id):
    customer_id = request.session.get('customer_user_id')
    if customer_id is None:
        messages.info(request, 'Please sign in to view your booking.')
        return redirect('user_login')

    customer = User.objects.filter(pk=customer_id).first()
    if customer is None:
        request.session.pop('customer_user_id', None)
        messages.info(request, 'Please sign in again.')
        return redirect('user_login')

    booking = get_object_or_404(
        Booking.objects.select_related('taxi', 'taxi__driver'),
        pk=booking_id,
        user=customer,
    )
    return render(request, 'core/booking_confirmation.html', {
        'booking': booking,
    })
    

def driver_dashboard(request):
    driver_id = request.session.get('driver_user_id')
    if driver_id is None:
        return redirect('driver_login')

    driver = Driver.objects.filter(pk=driver_id).first()
    if driver is None:
        request.session.pop('driver_user_id', None)
        messages.info(request, 'Please sign in to continue.')
        return redirect('driver_login')

    return render(request, 'core/driver_dashboard.html', {'driver': driver})


@require_POST
def user_logout(request):
    request.session.pop('customer_user_id', None)
    messages.success(request, 'You have been signed out.')
    return redirect('user_login')


@require_POST
def driver_logout(request):
    request.session.pop('driver_user_id', None)
    messages.success(request, 'You have been signed out.')
    return redirect('driver_login')


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
def admin_dashboard(request):
    user_model = get_user_model()
    context = {
        'total_users': user_model.objects.count(),
        'total_admins': user_model.objects.filter(is_staff=True).count(),
        'total_customers': User.objects.count(),
        'total_drivers': Driver.objects.count(),
    }
    return render(request, 'core/admin_dashboard.html', context)


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
def admin_drivers(request):
    search_form = DriverSearchForm(request.GET)
    search_form.is_valid()
    search_query = search_form.cleaned_data['q']
    drivers = Driver.objects.order_by('name')
    if search_query:
        drivers = drivers.filter(
            Q(name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(license_number__icontains=search_query)
            | Q(mobile__icontains=search_query),
        )

    return render(
        request,
        'core/admin_drivers.html',
        {
            'drivers': drivers,
            'search_form': search_form,
            'search_query': search_query,
        },
    )


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
def admin_driver_detail(request, driver_id):
    driver = get_object_or_404(Driver, pk=driver_id)
    return render(
        request,
        'core/admin_driver_detail.html',
        {'driver': driver},
    )


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
@require_POST
def admin_driver_delete(request, driver_id):
    driver = get_object_or_404(Driver, pk=driver_id)
    driver.delete()
    messages.success(request, 'Driver deleted successfully.')
    return redirect('admin_drivers')


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
def admin_users(request):
    search_form = UserSearchForm(request.GET)
    search_form.is_valid()
    search_query = search_form.cleaned_data['q']
    users = User.objects.all()
    if search_query:
        users = users.filter(
            Q(name__icontains=search_query) | Q(email__icontains=search_query),
        )

    return render(
        request,
        'core/admin_users.html',
        {
            'users': users,
            'search_form': search_form,
            'search_query': search_query,
        },
    )


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
def admin_user_detail(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    return render(
        request,
        'core/admin_user_detail.html',
        {'user_record': user},
    )


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
def admin_user_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'User details updated successfully.')
        return redirect('admin_users')

    return render(
        request,
        'core/admin_user_edit.html',
        {'form': form, 'user_record': user},
    )


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
@require_POST
def admin_user_delete(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.delete()
    messages.success(request, 'User deleted successfully.')
    return redirect('admin_users')


@user_passes_test(lambda user: user.is_authenticated and user.is_staff,
                  login_url='admin_login')
def admin_register(request):
    if request.method == 'POST':
        form = AdminRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                admin_user = form.save()
                AdminAccount.objects.create(user=admin_user)
            messages.success(request, 'Admin account created successfully.')
            return redirect('admin_register')
    else:
        form = AdminRegistrationForm()

    return render(request, 'core/admin_register.html', {'form': form})


def admin_forgot_password(request):
    if request.method == 'POST':
        request.session.pop('admin_password_reset_token', None)
        request.session.pop('admin_password_reset_verified_token', None)
        email = request.POST.get('email', '').strip()
        user_model = get_user_model()
        eligible_users = []
        if email:
            eligible_users = [
                user for user in user_model.objects.filter(
                    email__iexact=email,
                    is_staff=True,
                    is_active=True,
                )
                if user.has_usable_password()
            ]

        if len(eligible_users) == 1:
            user = eligible_users[0]
            otp = f'{secrets.randbelow(1_000_000):06d}'
            expires_at = timezone.now() + timedelta(minutes=10)

            with transaction.atomic():
                AdminPasswordResetOTP.objects.filter(
                    user=user,
                    is_used=False,
                ).delete()
                challenge = AdminPasswordResetOTP.objects.create(
                    user=user,
                    otp_hash=make_password(otp),
                    expires_at=expires_at,
                )
                send_mail(
                    subject='Taxi Booking System admin password reset',
                    message=(
                        f'Your admin password reset code is {otp}. '
                        'It expires in 10 minutes. If you did not request '
                        'this code, you can ignore this email.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

            request.session['admin_password_reset_token'] = str(challenge.token)

        # Do not disclose whether an email belongs to an admin account.
        return redirect('admin_forgot_password_done')

    return render(request, 'core/admin_forgot_password.html')


def admin_forgot_password_done(request):
    return render(request, 'core/admin_forgot_password_done.html')


def admin_reset_otp(request):
    token = request.session.get('admin_password_reset_token')
    if not token:
        return render(
            request,
            'core/admin_reset_otp.html',
            {'expired': True},
        )

    try:
        challenge = AdminPasswordResetOTP.objects.select_related('user').get(
            token=uuid.UUID(token),
        )
    except (AdminPasswordResetOTP.DoesNotExist, ValueError):
        request.session.pop('admin_password_reset_token', None)
        request.session.pop('admin_password_reset_verified_token', None)
        return render(
            request,
            'core/admin_reset_otp.html',
            {'expired': True},
        )

    if (
        challenge.is_used
        or not challenge.user.is_active
        or not challenge.user.is_staff
        or challenge.expires_at <= timezone.now()
    ):
        request.session.pop('admin_password_reset_token', None)
        request.session.pop('admin_password_reset_verified_token', None)
        return render(
            request,
            'core/admin_reset_otp.html',
            {'expired': True},
        )

    if challenge.attempts >= 5:
        return render(
            request,
            'core/admin_reset_otp.html',
            {'locked': True},
        )

    verified = (
        request.session.get('admin_password_reset_verified_token') == token
    )
    form = SetPasswordForm(
        challenge.user,
        request.POST if request.method == 'POST' and verified else None,
    ) if verified else None
    error = None
    if request.method == 'POST':
        if not verified:
            otp = request.POST.get('otp', '').strip()
            if len(otp) != 6 or not otp.isdigit() or not check_password(
                otp,
                challenge.otp_hash,
            ):
                challenge.attempts += 1
                challenge.save(update_fields=['attempts'])
                error = 'The verification code is invalid.'
                if challenge.attempts >= 5:
                    return render(
                        request,
                        'core/admin_reset_otp.html',
                        {'locked': True},
                    )
            else:
                request.session[
                    'admin_password_reset_verified_token'
                ] = token
                verified = True
                form = SetPasswordForm(challenge.user)
        elif form.is_valid():
            with transaction.atomic():
                form.save()
                challenge.is_used = True
                challenge.save(update_fields=['is_used'])
            request.session.pop('admin_password_reset_token', None)
            request.session.pop('admin_password_reset_verified_token', None)
            messages.success(
                request,
                'Your password has been reset. You can now log in.',
            )
            return redirect('admin_login')

    return render(
        request,
        'core/admin_reset_otp.html',
        {'form': form, 'error': error, 'verified': verified},
    )


@require_POST
def admin_logout(request):
    logout(request)
    return redirect('admin_login')

@user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url='admin_login',
)
def admin_add_taxi(request):
    if request.method == 'POST':
        form = TaxiForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Taxi added successfully!'
            )
            return redirect('admin_add_taxi')
    else:
        form = TaxiForm()

    return render(
        request,
        'core/admin_add_taxi.html',
        {'form': form},
    )
    
    
# List all taxis
@user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url='admin_login',
)
def admin_taxi_list(request):
    taxis = Taxi.objects.select_related('driver').order_by('-id')
    search_form = TaxiSearchForm(request.GET)
    search_form.is_valid()
    search_query = search_form.cleaned_data['q']

    if search_query:
        taxis = taxis.filter(
            Q(number__icontains=search_query)
            | Q(source__icontains=search_query)
            | Q(destination__icontains=search_query),
        )

    return render(
        request,
        'core/admin_taxi_list.html',
        {
            'taxis': taxis,
            'search_form': search_form,
            'search_query': search_query,
        },
    )


# View taxi details
@user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url='admin_login',
)
def admin_taxi_detail(request, taxi_id):
    taxi = get_object_or_404(
        Taxi.objects.select_related('driver'),
        pk=taxi_id,
    )

    return render(
        request,
        'core/admin_taxi_detail.html',
        {'taxi': taxi},
    )


# Edit taxi
@user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url='admin_login',
)
def admin_taxi_edit(request, taxi_id):
    taxi = get_object_or_404(Taxi, pk=taxi_id)

    if request.method == 'POST':
        form = TaxiForm(request.POST, instance=taxi)

        if form.is_valid():
            form.save()
            messages.success(request, 'Taxi updated successfully!')
            return redirect('admin_taxi_list')
    else:
        form = TaxiForm(instance=taxi)

    return render(
        request,
        'core/admin_taxi_edit.html',
        {'form': form, 'taxi': taxi},
    )


# Delete taxi after confirmation
@user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url='admin_login',
)
def admin_taxi_delete(request, taxi_id):
    taxi = get_object_or_404(Taxi, pk=taxi_id)

    if request.method == 'POST':
        taxi.delete()
        messages.success(request, 'Taxi deleted successfully!')
        return redirect('admin_taxi_list')

    return render(
        request,
        'core/admin_taxi_delete.html',
        {'taxi': taxi},
    )
