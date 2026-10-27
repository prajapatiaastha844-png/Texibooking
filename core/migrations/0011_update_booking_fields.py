from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_booking'),
    ]

    operations = [
        migrations.RenameField(
            model_name='booking',
            old_name='customer',
            new_name='user',
        ),
        migrations.RenameField(
            model_name='booking',
            old_name='booked_at',
            new_name='date',
        ),
        migrations.AlterField(
            model_name='booking',
            name='status',
            field=models.CharField(
                choices=[
                    ('Pending', 'Pending'),
                    ('Confirmed', 'Confirmed'),
                    ('Cancelled', 'Cancelled'),
                ],
                default='Pending',
                max_length=20,
            ),
        ),
    ]
