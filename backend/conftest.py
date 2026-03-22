"""
Root pytest configuration for the OVS backend.

Markers
-------
integration
    Tests that require live external services (Redis broker, real Celery worker).
    Skipped by default; run with:  pytest -m integration --run-integration
"""
import pytest


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
