
from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_login, name='admin_login'),
    path('login/', views.user_login, name='user_login'),
    path('my-dashboard/', views.user_dashboard, name='user_dashboard'),
    path(
        'my-dashboard/taxis/<int:taxi_id>/',
        views.user_taxi_detail,
        name='user_taxi_detail',
    ),
    
    
    path(
        'my-dashboard/taxis/<int:taxi_id>/book/',
        views.book_taxi,
        name='book_taxi',
    ),
    path(
        'my-dashboard/bookings/<int:booking_id>/confirmation/',
        views.booking_confirmation,
        name='booking_confirmation',
    ),
    
    path('logout/user/', views.user_logout, name='user_logout'),
    path('driver/login/', views.driver_login, name='driver_login'),
    path(
        'driver/dashboard/',
        views.driver_dashboard,
        name='driver_dashboard',
    ),
    path('logout/driver/', views.driver_logout, name='driver_logout'),
    path(
        'driver/forgot-password/',
        views.driver_forgot_password,
        name='driver_forgot_password',
    ),
    path(
        'driver/reset-password/verify/',
        views.driver_reset_otp,
        name='driver_reset_otp',
    ),
    path(
        'user/forgot-password/',
        views.user_forgot_password,
        name='user_forgot_password',
    ),
    path(
        'user/reset-password/verify/',
        views.user_reset_otp,
        name='user_reset_otp',
    ),
    path('signup/', views.user_register, name='user_register'),
    path('driver/signup/', views.driver_register, name='driver_register'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('drivers/', views.admin_drivers, name='admin_drivers'),
    path(
        'drivers/<int:driver_id>/',
        views.admin_driver_detail,
        name='admin_driver_detail',
    ),
    path(
        'drivers/<int:driver_id>/delete/',
        views.admin_driver_delete,
        name='admin_driver_delete',
    ),
    path('users/', views.admin_users, name='admin_users'),
    path('users/<int:user_id>/', views.admin_user_detail, name='admin_user_detail'),
    path('users/<int:user_id>/edit/', views.admin_user_edit, name='admin_user_edit'),
    path('users/<int:user_id>/delete/', views.admin_user_delete, name='admin_user_delete'),
    path('register/', views.admin_register, name='admin_register'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('forgot-password/', views.admin_forgot_password, name='admin_forgot_password'),
    path(
        'forgot-password/done/',
        views.admin_forgot_password_done,
        name='admin_forgot_password_done',
    ),
    path(
        'reset/verify/',
        views.admin_reset_otp,
        name='admin_reset_otp',
    ),
    
    path(
    'taxis/add/',
    views.admin_add_taxi,
    name='admin_add_taxi',
),
    
    
    # Taxi management
    path(
        'taxis/',
        views.admin_taxi_list,
        name='admin_taxi_list',
    ),
    path(
        'taxis/<int:taxi_id>/',
        views.admin_taxi_detail,
        name='admin_taxi_detail',
    ),
    path(
        'taxis/<int:taxi_id>/edit/',
        views.admin_taxi_edit,
        name='admin_taxi_edit',
    ),
    path(
        'taxis/<int:taxi_id>/delete/',
        views.admin_taxi_delete,
        name='admin_taxi_delete',
    ),

]
