from django.db import migrations


class Migration(migrations.Migration):
    """No-op: models moved to apps.users."""

    dependencies = [
        ('authentication', '0004_user_two_factor_backup_codes'),
    ]
    operations = []
