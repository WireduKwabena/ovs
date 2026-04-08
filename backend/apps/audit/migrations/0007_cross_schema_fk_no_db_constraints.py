"""
Drop DB-level FK constraints from AuditLog that point to AUTH_USER_MODEL
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
        ("audit", "0006_add_scope_context_fields"),
    ]

    operations = [
        # AuditLog.user
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("audit_logs", "user_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="auditlog",
                    name="user",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # AuditLog.admin_user
        migrations.SeparateDatabaseAndState(
            database_operations=[_drop_fk("audit_logs", "admin_user_id")],
            state_operations=[
                migrations.AlterField(
                    model_name="auditlog",
                    name="admin_user",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="admin_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
    ]
