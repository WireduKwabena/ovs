"""
Integration tests for verify_document_async against a live Redis broker.

Two test classes with different execution modes:

TestVerifyDocumentBrokerSerialization
    Uses CELERY_TASK_ALWAYS_EAGER=True.  Tasks execute in-process, but
    arguments are round-tripped through JSON to verify correct serialisation.
    These tests only need Redis to be reachable; no worker process required.

TestVerifyDocumentLiveWorker
    Spawns a real Celery worker subprocess (--pool=solo) connected to the
    same test database that pytest-django has set up.  Tasks are dispatched
    via apply_async() and results are retrieved from the Redis result backend.
    This class requires both Redis and a working PostgreSQL test database.

Run all integration tests:
    pytest apps/applications/test_verify_document_integration.py \\
           --run-integration -v

Run only the live-worker tests:
    pytest apps/applications/test_verify_document_integration.py \\
           --run-integration -v -k LiveWorker
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Redis reachability guard
# ---------------------------------------------------------------------------

def _redis_is_reachable(url: str | None = None) -> bool:
    try:
        import redis  # type: ignore[import]
        broker_url = url or os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
        client = redis.from_url(broker_url, socket_connect_timeout=2)
        client.ping()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.django_db(transaction=True),
]


# ---------------------------------------------------------------------------
# Shared DB fixture helpers (function-scoped, committed — visible to worker)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _check_redis():
    if not _redis_is_reachable():
        pytest.skip("Redis broker is not reachable — skipping broker integration tests.")


@pytest.fixture()
def officer(django_user_model):
    return django_user_model.objects.create_user(
        email="broker_officer@integration.test",
        password="Pass1234!",
        user_type="internal",
        first_name="Broker",
        last_name="Officer",
    )


@pytest.fixture()
def org():
    from apps.tenants.models import Organization
    return Organization.objects.create(
        name="Broker Test Agency",
        code="broker-test-agency",
        organization_type="agency",
        is_active=True,
    )


@pytest.fixture()
def subscription(org):
    from apps.billing.models import BillingSubscription
    return BillingSubscription.objects.create(
        provider="sandbox",
        status="complete",
        payment_status="paid",
        plan_id="starter",
        plan_name="Starter",
        billing_cycle="monthly",
        payment_method="card",
        amount_usd="149.00",
        reference=f"OVS-BROKER-STARTER-{str(org.id)[:8]}",
    )


@pytest.fixture()
def membership(officer, org):
    from apps.governance.models import OrganizationMembership
    return OrganizationMembership.objects.create(
        user=officer,
        membership_role="vetting_officer",
        is_active=True,
        is_default=True,
    )


@pytest.fixture()
def vetting_case(officer, org, subscription, membership):
    from apps.candidates.models import Candidate, CandidateEnrollment
    from apps.campaigns.models import VettingCampaign
    from apps.applications.models import VettingCase

    candidate = Candidate.objects.create(
        first_name="Broker",
        last_name="Candidate",
        email="broker.candidate@integration.test",
        consent_ai_processing=True,
    )
    campaign = VettingCampaign.objects.create(
        name="Broker Test Campaign",
        initiated_by=officer,
    )
    enrollment = CandidateEnrollment.objects.create(
        campaign=campaign,
        candidate=candidate,
        status="in_progress",
    )
    return VettingCase.objects.create(
        applicant=officer,
        candidate_enrollment=enrollment,
        assigned_to=officer,
        position_applied="Broker Test Position",
        priority="medium",
        status="document_upload",
    )


@pytest.fixture()
def queued_document(vetting_case):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.applications.models import Document

    return Document.objects.create(
        case=vetting_case,
        document_type="passport",
        original_filename="passport_integration.pdf",
        file=SimpleUploadedFile(
            "passport_integration.pdf",
            b"%PDF-1.4 integration test content",
            content_type="application/pdf",
        ),
        file_size=33,
        mime_type="application/pdf",
        status="pending",
    )


# ---------------------------------------------------------------------------
# Live worker fixture
# ---------------------------------------------------------------------------

def _build_worker_env() -> dict[str, str]:
    """
    Build an environment dict for the Celery worker subprocess.

    Key decisions:
    - POSTGRES_DB is set to the TEST database name so the worker writes to the
      same DB that pytest-django's transaction=True tests have committed data to.
    - CELERY_RESULT_BACKEND uses Redis DB 3 (separate from the application DB 0)
      to avoid collisions with other test runs.
    - PLACEHOLDER_ML_ENABLED=true lets _run_document_analysis fall back to the
      stub without requiring trained model files or heavy CV/ML imports.
    - CELERY_EAGER=false ensures tasks execute asynchronously in the worker.
    """
    from django.conf import settings as django_settings  # noqa: PLC0415

    db = django_settings.DATABASES["default"]
    broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    # Use Redis DB 3 for results to avoid interfering with the main app result backend.
    result_backend = broker_url.rsplit("/", 1)[0] + "/3"

    return {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.development",
        "DEBUG": "true",
        "SECRET_KEY": "test-live-worker-integration-key-only",
        # Point the worker at the TEST database (pytest-django has already set NAME to the test DB).
        "POSTGRES_DB": db["NAME"],
        "POSTGRES_USER": str(db.get("USER", "postgres")),
        "POSTGRES_PASSWORD": str(db.get("PASSWORD", "")),
        "POSTGRES_HOST": str(db.get("HOST", "localhost")),
        "POSTGRES_PORT": str(db.get("PORT", "5432")),
        "PLACEHOLDER_ML_ENABLED": "true",
        "CELERY_EAGER": "false",
        "CELERY_BROKER_URL": broker_url,
        "CELERY_RESULT_BACKEND": result_backend,
    }


def _worker_is_ready(env: dict[str, str]) -> bool:
    """Probe the worker via 'celery inspect ping'. Returns True if a pong is received."""
    try:
        probe = subprocess.run(
            [sys.executable, "-m", "celery", "-A", "config", "inspect", "ping", "--timeout=2"],
            env=env,
            cwd=str(BACKEND_DIR),
            capture_output=True,
            timeout=8,
        )
        return b"pong" in probe.stdout or b"pong" in probe.stderr
    except (subprocess.TimeoutExpired, OSError):
        return False


@pytest.fixture(scope="module")
def live_celery_worker(_check_redis):
    """
    Module-scoped fixture: spawns a real Celery worker subprocess (--pool=solo)
    and waits up to 30 s for it to become ready.  Tears it down after the module.

    The worker connects to:
    - The same test PostgreSQL database that pytest-django has set up.
    - The same Redis broker, but uses DB 3 for the result backend.
    """
    env = _build_worker_env()

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "celery",
            "-A", "config",
            "worker",
            "--loglevel=error",
            "--pool=solo",
            "--concurrency=1",
        ],
        env=env,
        cwd=str(BACKEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + 30
    ready = False
    while time.monotonic() < deadline:
        if _worker_is_ready(env):
            ready = True
            break
        if proc.poll() is not None:
            # Worker process already died.
            break
        time.sleep(1.5)

    if not ready:
        proc.terminate()
        pytest.skip("Celery worker subprocess did not become ready in 30 s — skipping live worker tests.")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# Class 1: Serialisation-only tests (no live worker, Redis required)
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_check_redis")
class TestVerifyDocumentBrokerSerialization:
    """
    Tests that verify task argument serialisation and broker round-trip
    behaviour.  CELERY_TASK_ALWAYS_EAGER=True means execution is in-process,
    but args are serialised via JSON exactly as they would be over the broker.
    """

    @pytest.mark.usefixtures("subscription", "membership")
    def test_task_returns_success_result(self, queued_document, settings):
        """Basic smoke: task returns a well-formed success dict."""
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.PLACEHOLDER_ML_ENABLED = True

        from unittest.mock import patch
        from apps.applications.tasks import verify_document_async

        with patch("ai_ml_services.service.verify_document", side_effect=RuntimeError("no model")):
            result = verify_document_async.apply(args=[queued_document.id]).get(timeout=30)

        assert result["success"] is True
        assert result["document_id"] == queued_document.id
        assert result["status"] in {"verified", "flagged"}

    @pytest.mark.usefixtures("subscription", "membership")
    def test_integer_document_id_survives_json_round_trip(self, queued_document, settings):
        """Document IDs serialised to JSON and back still resolve the correct record."""
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.PLACEHOLDER_ML_ENABLED = True

        from unittest.mock import patch
        from apps.applications.tasks import verify_document_async

        serialised_id = json.loads(json.dumps(queued_document.id))

        with patch("ai_ml_services.service.verify_document", side_effect=RuntimeError("no model")):
            result = verify_document_async.apply(args=[serialised_id]).get(timeout=30)

        assert result["success"] is True
        assert result["document_id"] == queued_document.id

    @pytest.mark.usefixtures("subscription", "membership")
    def test_idempotency_guard_prevents_duplicate_results(self, queued_document, settings):
        """A second task dispatch for an already-processed document is skipped."""
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.PLACEHOLDER_ML_ENABLED = True

        from unittest.mock import patch
        from apps.applications.models import VerificationResult
        from apps.applications.tasks import verify_document_async

        with patch("ai_ml_services.service.verify_document", side_effect=RuntimeError("no model")):
            verify_document_async.apply(args=[queued_document.id]).get(timeout=30)
            first_count = VerificationResult.objects.filter(document=queued_document).count()
            result = verify_document_async.apply(args=[queued_document.id]).get(timeout=30)

        assert result.get("skipped") is True
        assert VerificationResult.objects.filter(document=queued_document).count() == first_count


# ---------------------------------------------------------------------------
# Class 2: Live worker tests (real subprocess + apply_async + .get())
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("live_celery_worker")
class TestVerifyDocumentLiveWorker:
    """
    Tests that dispatch tasks via apply_async() to a real Celery worker
    subprocess and retrieve results from the Redis result backend.

    This is a true end-to-end broker integration test:
    - apply_async() serialises the task and publishes it to the Redis broker.
    - The worker subprocess dequeues, deserialises, and executes it.
    - .get(timeout=30) polls the Redis result backend until the result arrives.
    - The test asserts both the returned result and the DB side-effects.
    """

    @pytest.mark.usefixtures("subscription", "membership")
    def test_task_executes_on_live_worker_and_returns_result(self, queued_document):
        """
        Core live-worker test: task is dispatched async and the result backend
        receives a well-formed success response from the worker process.
        """
        from apps.applications.tasks import verify_document_async

        async_result = verify_document_async.apply_async(args=[queued_document.id])
        result = async_result.get(timeout=30)

        assert result["success"] is True
        assert result["document_id"] == queued_document.id
        assert result["status"] in {"verified", "flagged"}

    @pytest.mark.usefixtures("subscription", "membership")
    def test_live_worker_writes_verification_result_to_db(self, queued_document):
        """
        DB side-effect test: the worker must have committed a VerificationResult
        row that the test process can read after .get() returns.
        """
        from apps.applications.models import VerificationResult
        from apps.applications.tasks import verify_document_async

        async_result = verify_document_async.apply_async(args=[queued_document.id])
        async_result.get(timeout=30)

        # The worker committed, so we can read the row without re-loading.
        assert VerificationResult.objects.filter(document=queued_document).exists(), (
            "VerificationResult was not written to the DB by the live worker."
        )

    @pytest.mark.usefixtures("subscription", "membership")
    def test_live_worker_updates_document_status(self, queued_document):
        """Document.status must be 'verified' or 'flagged' after the task completes."""
        from apps.applications.models import Document
        from apps.applications.tasks import verify_document_async

        async_result = verify_document_async.apply_async(args=[queued_document.id])
        async_result.get(timeout=30)

        queued_document.refresh_from_db()
        assert queued_document.status in {"verified", "flagged"}, (
            f"Unexpected document status after live worker run: {queued_document.status!r}"
        )

    @pytest.mark.usefixtures("subscription", "membership")
    def test_live_worker_idempotency_on_second_dispatch(self, queued_document):
        """
        Duplicate dispatches to the live worker must not produce a second
        VerificationResult row — the idempotency guard must fire in the worker.
        """
        from apps.applications.models import VerificationResult
        from apps.applications.tasks import verify_document_async

        # First dispatch — processes normally.
        verify_document_async.apply_async(args=[queued_document.id]).get(timeout=30)
        count_after_first = VerificationResult.objects.filter(document=queued_document).count()

        # Second dispatch — should be skipped.
        result = verify_document_async.apply_async(args=[queued_document.id]).get(timeout=30)

        assert result.get("skipped") is True, "Expected idempotency skip on second dispatch."
        assert (
            VerificationResult.objects.filter(document=queued_document).count()
            == count_after_first
        ), "Idempotency guard failed: a duplicate VerificationResult was created."
