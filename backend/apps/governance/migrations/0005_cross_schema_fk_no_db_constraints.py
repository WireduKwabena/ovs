"""
Drop DB-level FK constraints from TENANT_APP models that point to
AUTH_USER_MODEL (users_user), which lives in the public schema.

Cross-schema FK constraints can't be enforced by PostgreSQL when
search_path is set to the tenant schema only, and they cause
"relation users_user does not exist" errors during tenant schema
migrations.  Removing the DB constraint leaves the ORM relationship
intact — Django still validates referential integrity at the
application layer.

This migration is safe to run on both:
- Existing databases: constraints exist → SQL drops them.
- Fresh databases: constraints were never created (0001_initial was
  already updated to use db_constraint=False) → DO block is a no-op.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _drop_fk_if_exists(table, column):
    """Return a RunSQL that dynamically finds and drops the FK constraint."""
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
        ("governance", "0004_remove_organizationmembership_organization"),
    ]

    operations = [
        # OrganizationMembership.user
        migrations.SeparateDatabaseAndState(
            database_operations=[
                _drop_fk_if_exists("governance_organizationmembership", "user_id"),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="organizationmembership",
                    name="user",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="organization_memberships",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # Committee.created_by
        migrations.SeparateDatabaseAndState(
            database_operations=[
                _drop_fk_if_exists("governance_committee", "created_by_id"),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="committee",
                    name="created_by",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_committees",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
        # CommitteeMembership.user
        migrations.SeparateDatabaseAndState(
            database_operations=[
                _drop_fk_if_exists("governance_committeemembership", "user_id"),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="committeemembership",
                    name="user",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="committee_memberships",
                        to=settings.AUTH_USER_MODEL,
                        db_constraint=False,
                    ),
                ),
            ],
        ),
    ]
