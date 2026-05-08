from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0011_alter_document_document_type"),
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
                    ("resume", "Resume / CV"),
                    ("cover_letter", "Cover Letter"),
                    ("birth_certificate", "Birth Certificate"),
                    ("degree", "Educational Degree/Certificate"),
                    ("medical_certificate", "Medical Certificate"),
                    ("police_clearance", "Police Clearance"),
                    ("nomination_letter", "Nomination Letter"),
                    ("appointment_letter", "Appointment Letter"),
                    ("asset_declaration", "Asset Declaration"),
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
