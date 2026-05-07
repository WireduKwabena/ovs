# Generated to align Organization.organization_type with current model choices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0004_alter_organization_tier"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organization",
            name="organization_type",
            field=models.CharField(
                choices=[
                    ("ministry", "Ministry"),
                    ("agency", "Agency"),
                    ("committee_secretariat", "Committee Secretariat"),
                    ("executive_office", "Executive Office"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=30,
            ),
        ),
    ]
