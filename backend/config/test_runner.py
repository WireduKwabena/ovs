"""Custom test runner for single-schema test execution."""

from django.test.runner import DiscoverRunner


class AllSchemasTestRunner(DiscoverRunner):
    """Compatibility alias for the legacy test runner setting."""

    pass
