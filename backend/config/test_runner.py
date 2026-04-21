"""
Custom test runner for OVS.

django_tenants routes SHARED_APPS migrations to the public schema and
TENANT_APPS migrations to tenant-specific schemas.  The standard Django test
runner only runs `migrate` (which, through TenantSyncRouter, only applies
SHARED_APPS to the public schema), so TENANT_APP tables (governance, billing,
etc.) are never created and almost every test fails with "relation X does not
exist".

This runner fixes that by:
1. Temporarily allowing `users` app migrations to run in the public schema
   so that django.contrib.admin can create django_admin_log with its FK to
   users_user (AUTH_USER_MODEL).  Without this, admin.0001_initial's deferred
   FK constraint fails when users is in TENANT_APPS.
2. Purging any stale test_tenant schema left by a previous failed run, then
   creating a fresh tenant — which via TenantMixin.save() → create_schema()
   automatically applies all TENANT_APPS migrations to the new schema.
3. Switching the default connection to the test tenant schema so all test
   queries land in the right place.
4. Patching Organization.save() so that tests can freely call
   Organization.objects.create() without switching schemas manually.
   New tenant records are written to the public schema's tenants_organization
   table (using a momentary schema switch) but no new DB schema is created —
   tests run inside the single test_tenant schema throughout.
"""

from django.test.runner import DiscoverRunner
from django.db import connection


class AllSchemasTestRunner(DiscoverRunner):
    """Run all migrations (shared + tenant) before the tests execute."""

    TEST_TENANT_SCHEMA = "test_tenant"

    # TENANT_APPS that are also referenced by SHARED_APPS FK constraints and
    # therefore need to exist in the public schema for shared migrations to
    # succeed (e.g. django.contrib.admin -> users_user).
    _PUBLIC_SCHEMA_ALSO_MIGRATE = frozenset({"users"})

    def _purge_stale_test_tenant(self):
        """
        Drop any leftover test_tenant schema and its record from a previous
        failed run.  This must be called while connected to the public schema.
        """
        from django_tenants.utils import get_tenant_model

        TenantModel = get_tenant_model()

        # Delete any DB-level record first (avoids FK errors on schema drop).
        stale = TenantModel.objects.filter(schema_name=self.TEST_TENANT_SCHEMA).first()
        if stale is not None:
            try:
                # force_drop=True drops the PostgreSQL schema as well.
                stale.delete(force_drop=True)
                return  # schema already gone via force_drop
            except Exception:
                pass  # fall through to raw DROP SCHEMA below

        # Drop the schema directly in case no ORM record existed.
        schema = self.TEST_TENANT_SCHEMA.replace('"', '""')  # safe-quote
        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')

    def _patch_organization_save(self, test_tenant):
        """
        Monkey-patch Organization.save() so that tests can call
        Organization.objects.create() while connected to the tenant schema.

        The patch:
        - Briefly switches to the public schema for the INSERT (tenants_organization
          lives in public, and TenantMixin.save() raises if not in public).
        - Suppresses create_schema() so no new PostgreSQL schema is created per
          test organisation — all test queries stay in test_tenant.
        - Restores the tenant connection immediately after the save.

        Returns the original (unpatched) save callable so it can be restored in
        teardown_databases.
        """
        from apps.tenants.models import Organization

        _orig_save = Organization.save

        def _test_save(org_instance, verbosity=1, *args, **kwargs):
            # TenantMixin.save() uses _state.adding (not pk is None) because
            # UUID PKs are pre-assigned in __init__ before save() is called.
            is_new = org_instance._state.adding
            import uuid as _uuid
            from django_tenants.utils import schema_context

            if is_new:
                # Suppress schema creation; we don't need a real DB schema per
                # test organisation — all tests run inside the single test_tenant
                # schema.
                org_instance.auto_create_schema = False

                # If the caller didn't supply a schema_name, auto-generate a
                # unique one so the unique constraint on tenants_organization
                # doesn't clash when multiple test orgs are created in one test.
                if not org_instance.schema_name:
                    _slug = getattr(org_instance, "code", "") or str(org_instance.pk or "")
                    _slug = _slug[:20].replace("-", "_").lower()
                    org_instance.schema_name = f"t_{_slug}_{_uuid.uuid4().hex[:8]}"

            if connection.schema_name != "public":
                # Both new and existing org records live in the public schema's
                # tenants_organization table.  TenantMixin.save() raises if called
                # from a non-public schema, so always switch to public here.
                with schema_context("public"):
                    _orig_save(org_instance, verbosity=verbosity, *args, **kwargs)
                # schema_context.__exit__ restores the tenant connection.
            else:
                _orig_save(org_instance, verbosity=verbosity, *args, **kwargs)

        Organization.save = _test_save
        return _orig_save

    def setup_databases(self, **kwargs):
        # ── Step 1: patch the tenant router so users migrations also run in the
        # public schema, satisfying admin's FK constraint to users_user. ──────
        from django_tenants.routers import TenantSyncRouter

        _orig_allow_migrate = TenantSyncRouter.allow_migrate

        _extra = self._PUBLIC_SCHEMA_ALSO_MIGRATE

        def _patched_allow_migrate(router_self, db, app_label, model_name=None, **hints):
            if app_label in _extra:
                import sys
                print(f"[PATCH] allow_migrate: app={app_label} db={db} schema={connection.schema_name} → True", file=sys.stderr)
                return True
            result = _orig_allow_migrate(router_self, db, app_label, model_name=model_name, **hints)
            if app_label in ("admin", "users"):
                import sys
                print(f"[PATCH] allow_migrate: app={app_label} db={db} schema={connection.schema_name} → {result}", file=sys.stderr)
            return result

        TenantSyncRouter.allow_migrate = _patched_allow_migrate
        try:
            old_config = super().setup_databases(**kwargs)
        finally:
            TenantSyncRouter.allow_migrate = _orig_allow_migrate

        # ── Step 2: purge any stale schema, then create a fresh test tenant. ─
        # TenantMixin.save() → create_schema() automatically migrates all
        # TENANT_APPS into the new schema, so no explicit migrate_schemas call
        # is needed here.
        self._purge_stale_test_tenant()

        from django_tenants.utils import get_tenant_model, get_tenant_domain_model

        TenantModel = get_tenant_model()
        DomainModel = get_tenant_domain_model()

        tenant = TenantModel.objects.create(
            schema_name=self.TEST_TENANT_SCHEMA,
            code="test-tenant",
            name="Test Tenant",
        )

        # Attach a domain so middleware can find it later.
        DomainModel.objects.get_or_create(
            tenant=tenant,
            defaults={"domain": "testserver", "is_primary": True},
        )

        # ── Step 3: switch the current connection to the test tenant schema so
        # all test queries land in the right place. ───────────────────────────
        connection.set_tenant(tenant)

        # ── Step 4: patch Organization.save() so tests can create Organisation
        # records without switching schemas manually. ─────────────────────────
        self._orig_organization_save = self._patch_organization_save(tenant)

        return old_config

    def teardown_databases(self, old_config, **kwargs):
        # Restore the original Organization.save() before teardown.
        try:
            from apps.tenants.models import Organization
            if hasattr(self, "_orig_organization_save"):
                Organization.save = self._orig_organization_save
        except Exception:
            pass

        connection.set_schema_to_public()
        from django_tenants.utils import get_tenant_model
        TenantModel = get_tenant_model()
        try:
            tenant = TenantModel.objects.filter(
                schema_name=self.TEST_TENANT_SCHEMA
            ).first()
            if tenant is not None:
                tenant.delete(force_drop=True)
        except Exception:
            pass
        super().teardown_databases(old_config, **kwargs)
