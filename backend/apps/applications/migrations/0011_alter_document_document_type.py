from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0010_extend_case_info_request_with_templates_and_attachments"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="document_type",
            field=models.CharField(
                choices=[
                    ("id_card", "National ID Card"),
                    ("passport", "Passport"),
                    ("drivers_license", "Driver's License"),
                    ("birth_certificate", "Birth Certificate"),
                    ("degree", "Educational Degree/Certificate"),
                    ("certificate", "Certificate"),
                    ("diploma", "Diploma"),
                    ("transcript", "Academic Transcript"),
                    ("employment_letter", "Employment Letter"),
                    ("reference_letter", "Reference Letter"),
                    ("pay_slip", "Pay Slip"),
                    ("bank_statement", "Bank Statement"),
                    ("utility_bill", "Utility Bill"),
                    ("other", "Other"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
    ]
