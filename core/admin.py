
from django.contrib import admin
from .models import User
from .models import Driver

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'email',
        'license_number',
        'mobile',
    )
    search_fields = ('name', 'email', 'license_number')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'mobile')
    search_fields = ('name', 'email', 'mobile')
    list_display_links = ('id', 'name')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('password',)
        return ()
