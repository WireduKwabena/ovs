"""
Custom test runner for OVS.

django_tenants routes SHARED_APPS migrations to the public schema and
TENANT_APPS migrations to tenant-specific schemas.  The standard Django test
runner only runs `migrate` (which, through TenantSyncRouter, only applies
SHARED_APPS to the public schema), so TENANT_APP tables (governance, billing,
etc.) are never created and almost every test fails with "relation X does not
exist".

This runner fixes that by creating a temporary "public" tenant and running
`migrate_schemas --tenant` so all TENANT_APPS tables are created in a
test tenant schema.  Tests then connect to that tenant schema for the
duration of the test run.
"""

from django.core.management import call_command
from django.test.runner import DiscoverRunner
from django.db import connection


class AllSchemasTestRunner(DiscoverRunner):
    """Run all migrations (shared + tenant) before the tests execute."""

    TEST_TENANT_SCHEMA = "test_tenant"

    def setup_databases(self, **kwargs):
        old_config = super().setup_databases(**kwargs)

        from django_tenants.utils import get_tenant_model, get_tenant_domain_model

        TenantModel = get_tenant_model()
        DomainModel = get_tenant_domain_model()

        # Create a test tenant (if it doesn't already exist).
        tenant, _ = TenantModel.objects.get_or_create(
            schema_name=self.TEST_TENANT_SCHEMA,
        )

        # Attach a domain so middleware can find it later.
        DomainModel.objects.get_or_create(
            tenant=tenant,
            defaults={"domain": "testserver", "is_primary": True},
        )

        # Migrate TENANT_APPS into the test tenant schema.
        call_command(
            "migrate_schemas",
            tenant=True,
            schema_name=self.TEST_TENANT_SCHEMA,
            interactive=False,
            verbosity=0,
        )

        # Switch the current connection to this schema so all test queries
        # land in the right place.
        connection.set_tenant(tenant)

        return old_config

    def teardown_databases(self, old_config, **kwargs):
        connection.set_schema_to_public()
        from django_tenants.utils import get_tenant_model
        TenantModel = get_tenant_model()
        try:
            TenantModel.objects.filter(schema_name=self.TEST_TENANT_SCHEMA).first()
        except Exception:
            pass
        super().teardown_databases(old_config, **kwargs)
