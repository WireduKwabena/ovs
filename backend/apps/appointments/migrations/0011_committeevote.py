import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0010_cross_schema_fk_no_db_constraints"),
        ("governance", "0005_cross_schema_fk_no_db_constraints"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommitteeVote",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "appointment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="committee_votes",
                        to="appointments.appointmentrecord",
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="committee_votes",
                        to="appointments.approvalstage",
                    ),
                ),
                (
                    "committee_membership",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="committee_votes",
                        to="governance.committeemembership",
                    ),
                ),
                (
                    "vote",
                    models.CharField(
                        choices=[("approve", "Approve"), ("reject", "Reject"), ("abstain", "Abstain")],
                        max_length=10,
                    ),
                ),
                ("reason_note", models.TextField(blank=True)),
                ("voted_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["voted_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="committeevote",
            constraint=models.UniqueConstraint(
                fields=["appointment", "stage", "committee_membership"],
                name="uniq_committee_vote_appointment_stage_member",
            ),
        ),
        migrations.AddIndex(
            model_name="committeevote",
            index=models.Index(fields=["appointment", "stage"], name="appt_committeevote_appt_stage_idx"),
        ),
    ]
