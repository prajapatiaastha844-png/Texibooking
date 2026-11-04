from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_update_booking_status_choices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='booking',
            name='status',
            field=models.CharField(
                choices=[
                    ('Pending', 'Pending'),
                    ('Approved', 'Approved'),
                    ('Rejected', 'Rejected'),
                    ('Cancelled', 'Cancelled'),
                ],
                default='Pending',
                max_length=20,
            ),
        ),
    ]
