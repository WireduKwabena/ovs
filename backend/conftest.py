"""
Root pytest configuration for the OVS backend.

Markers
-------
integration
    Tests that require live external services (Redis broker, real Celery worker).
    Skipped by default; run with:  pytest -m integration --run-integration
"""
import pytest


TEST_TENANT_SCHEMA = "test_tenant"
_TEST_TENANT = None


def _build_schema_name(org_instance) -> str:
    import uuid

    seed = (getattr(org_instance, "code", "") or str(getattr(org_instance, "pk", "") or "")).lower()
    seed = seed.replace("-", "_")[:20] or "org"
    return f"t_{seed}_{uuid.uuid4().hex[:8]}"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require live external services (Redis, etc.).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test requiring live services.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(
        reason="Integration test — pass --run-integration to execute."
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_tenant_for_pytest(django_db_setup, django_db_blocker):
    """Create/switch to a dedicated tenant schema so tenant-app tables exist in tests."""
    global _TEST_TENANT

    with django_db_blocker.unblock():
        from django.db import connection
        from django_tenants.utils import get_tenant_domain_model, get_tenant_model

        TenantModel = get_tenant_model()
        DomainModel = get_tenant_domain_model()

        stale = TenantModel.objects.filter(schema_name=TEST_TENANT_SCHEMA).first()
        if stale is not None:
            try:
                stale.delete(force_drop=True)
            except Exception:
                pass

        tenant = TenantModel.objects.create(
            schema_name=TEST_TENANT_SCHEMA,
            code="test-tenant",
            name="Test Tenant",
        )

        DomainModel.objects.get_or_create(
            tenant=tenant,
            defaults={"domain": "testserver", "is_primary": True},
        )
        connection.set_tenant(tenant)
        _TEST_TENANT = tenant

    yield

    with django_db_blocker.unblock():
        from django.db import connection
        from django_tenants.utils import get_tenant_model

        connection.set_schema_to_public()
        TenantModel = get_tenant_model()
        tenant = TenantModel.objects.filter(schema_name=TEST_TENANT_SCHEMA).first()
        if tenant is not None:
            try:
                tenant.delete(force_drop=True)
            except Exception:
                pass
        _TEST_TENANT = None


@pytest.fixture(scope="session", autouse=True)
def _patch_organization_save_for_pytest(django_db_setup):
    """Allow Organization.objects.create() in tenant schema without creating extra schemas."""
    from django.db import connection
    from django_tenants.utils import schema_context

    from apps.tenants.models import Organization

    original_save = Organization.save

    def _test_save(org_instance, verbosity=1, *args, **kwargs):
        is_new = org_instance._state.adding
        if is_new:
            org_instance.auto_create_schema = False
            if not org_instance.schema_name:
                org_instance.schema_name = _build_schema_name(org_instance)

        if connection.schema_name != "public":
            with schema_context("public"):
                return original_save(org_instance, verbosity=verbosity, *args, **kwargs)
        return original_save(org_instance, verbosity=verbosity, *args, **kwargs)

    Organization.save = _test_save
    yield
    Organization.save = original_save


@pytest.fixture(autouse=True)
def _force_tenant_schema_per_test():
    """Reset to the test tenant each test without forcing DB access for SimpleTestCase."""
    from django.db import connection

    if _TEST_TENANT is not None:
        connection.set_tenant(_TEST_TENANT)
    yield
