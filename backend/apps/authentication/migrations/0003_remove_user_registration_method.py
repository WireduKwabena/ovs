from django.db import migrations


class Migration(migrations.Migration):
    """No-op: models moved to apps.users."""

    dependencies = [
        ('authentication', '0002_user_registration_method_passwordresettoken'),
    ]
    operations = []
