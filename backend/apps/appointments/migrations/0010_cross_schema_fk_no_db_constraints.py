"""
Drop DB-level FK constraints from TENANT_APP appointment models that point to
AUTH_USER_MODEL (users_user), which lives in the public schema.
See governance/0005_cross_schema_fk_no_db_constraints.py for full rationale.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _drop_fk(table, column):
    return migrations.RunSQL(
        sql=f"""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN (
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
                WHERE t.relname = '{table}'
                  AND c.contype = 'f'
                  AND a.attname = '{column}'
            ) LOOP
                EXECUTE 'ALTER TABLE {table} DROP CONSTRAINT ' || quote_ident(r.conname);
            END LOOP;
        END $$;
        """,
        reverse_sql=migrations.RunSQL.noop,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0009_remove_appointmentrecord_idx_appt_org_status_and_more"),
    ]

    operations = [
        # AppointmentRecord.nominated_by_user
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("appointments_appointmentrecord", "nominated_by_user_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="appointmentrecord",
                    name="nominated_by_user",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="nominations_submitted",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # AppointmentRecord.final_decision_by_user
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("appointments_appointmentrecord", "final_decision_by_user_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="appointmentrecord",
                    name="final_decision_by_user",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appointment_decisions",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # AppointmentStageAction.actor
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("appointments_appointmentstageaction", "actor_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="appointmentstageaction",
                    name="actor",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # ApprovalStageTemplate.created_by
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("appointments_approvalstagetemplate", "created_by_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="approvalstagetemplate",
                    name="created_by",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_approval_stage_templates",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # AppointmentPublication.published_by
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("appointments_appointmentpublication", "published_by_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="appointmentpublication",
                    name="published_by",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="published_appointment_records",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # AppointmentPublication.revoked_by
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("appointments_appointmentpublication", "revoked_by_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="appointmentpublication",
                    name="revoked_by",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="revoked_appointment_records",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
    ]
