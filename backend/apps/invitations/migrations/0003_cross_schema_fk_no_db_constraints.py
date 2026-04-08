"""
Drop DB-level FK constraints from invitation models that point to AUTH_USER_MODEL
(users_user), which lives in the public schema.
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
        ("invitations", "0002_candidateaccesspass_candidateaccesssession_and_more"),
    ]

    operations = [
        # Invitation.created_by
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("invitations_invitation", "created_by_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="invitation",
                    name="created_by",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_invitations",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # CandidateAccessPass.issued_by
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("invitations_candidateaccesspass", "issued_by_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="candidateaccesspass",
                    name="issued_by",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="issued_candidate_access_passes",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
    ]
