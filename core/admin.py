
from django.contrib import admin
from .models import Driver, Taxi, TaxiDetails, User, Booking

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'email',
        'license_number',
        'mobile',
        'taxi_number',
    )
    search_fields = ('name', 'email', 'license_number')


@admin.register(Taxi)
class TaxiAdmin(admin.ModelAdmin):
    list_display = (
        'number',
        'type',
        'source',
        'destination',
        'price',
        'availability',
        'driver',
    )
    list_filter = ('type', 'availability')
    search_fields = ('number', 'source', 'destination', 'driver__name')


@admin.register(TaxiDetails)
class TaxiDetailsAdmin(admin.ModelAdmin):
    list_display = ('source', 'destination', 'driver')
    search_fields = ('source', 'destination', 'driver__name')


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'mobile')
    search_fields = ('name', 'email', 'mobile')
    list_display_links = ('id', 'name')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('password',)
        return ()


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'taxi', 'date', 'status')
    list_filter = ('status', 'date')
    search_fields = ('user__name', 'taxi__number')