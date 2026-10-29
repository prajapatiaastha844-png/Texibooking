from django.db import migrations, models


def migrate_confirmed_to_approved(apps, schema_editor):
    Booking = apps.get_model('core', 'Booking')
    Booking.objects.filter(status='Confirmed').update(status='Approved')


def migrate_approved_to_confirmed(apps, schema_editor):
    Booking = apps.get_model('core', 'Booking')
    Booking.objects.filter(status='Approved').update(status='Confirmed')


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_update_booking_fields'),
    ]

    operations = [
        migrations.RunPython(
            migrate_confirmed_to_approved,
            migrate_approved_to_confirmed,
        ),
        migrations.AlterField(
            model_name='booking',
            name='status',
            field=models.CharField(
                choices=[
                    ('Pending', 'Pending'),
                    ('Approved', 'Approved'),
                    ('Cancelled', 'Cancelled'),
                ],
                default='Pending',
                max_length=20,
            ),
        ),
    ]
