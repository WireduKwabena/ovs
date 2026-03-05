from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_billingsubscription_registration_consumed_at_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="billingsubscription",
            name="provider",
            field=models.CharField(
                choices=[("stripe", "Stripe"), ("paystack", "Paystack"), ("sandbox", "Sandbox")],
                default="stripe",
                max_length=32,
            ),
        ),
    ]

