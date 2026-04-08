"""
Drop DB-level FK constraint from BackgroundCheck.submitted_by that points to
AUTH_USER_MODEL (users_user), which lives in the public schema.
See governance/0005_cross_schema_fk_no_db_constraints.py for full rationale.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("background_checks", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    DO $$
                    DECLARE r RECORD;
                    BEGIN
                        FOR r IN (
                            SELECT c.conname
                            FROM pg_constraint c
                            JOIN pg_class t ON t.oid = c.conrelid
                            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
                            WHERE t.relname = 'background_checks_backgroundcheck'
                              AND c.contype = 'f'
                              AND a.attname = 'submitted_by_id'
                        ) LOOP
                            EXECUTE 'ALTER TABLE background_checks_backgroundcheck DROP CONSTRAINT ' || quote_ident(r.conname);
                        END LOOP;
                    END $$;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="backgroundcheck",
                    name="submitted_by",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submitted_background_checks",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
    ]
