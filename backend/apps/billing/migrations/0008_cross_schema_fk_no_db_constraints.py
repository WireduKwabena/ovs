"""
Drop DB-level FK constraint from OrganizationOnboardingToken.created_by
which points to AUTH_USER_MODEL (users_user) in the public schema.

See governance/0005_cross_schema_fk_no_db_constraints.py for full context.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0007_remove_billingsubscription_organization"),
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
                            WHERE t.relname = 'billing_organizationonboardingtoken'
                              AND c.contype = 'f'
                              AND a.attname = 'created_by_id'
                        ) LOOP
                            EXECUTE 'ALTER TABLE billing_organizationonboardingtoken DROP CONSTRAINT ' || quote_ident(r.conname);
                        END LOOP;
                    END $$;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="organizationonboardingtoken",
                    name="created_by",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_organization_onboarding_tokens",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
    ]
