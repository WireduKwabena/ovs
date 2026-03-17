"""Tests for the purge_expired_data management command."""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.core.management.commands.purge_expired_data import (
    ALL_SCOPES,
    SCOPE_AUDIT_LOGS,
    SCOPE_BACKGROUND_CHECKS,
    SCOPE_BIOMETRIC,
    SCOPE_PII,
    Command,
    _cutoff,
    _purge_audit_logs,
    _purge_background_checks,
    _purge_biometric,
    _purge_pii,
)


class CutoffTests(SimpleTestCase):
    def test_cutoff_is_in_the_past(self):
        from django.utils import timezone
        cut = _cutoff(30)
        self.assertLess(cut, timezone.now())

    def test_cutoff_365_days_is_about_one_year_ago(self):
        from datetime import timedelta
        from django.utils import timezone
        cut = _cutoff(365)
        expected = timezone.now() - timedelta(days=365)
        self.assertAlmostEqual(
            cut.timestamp(), expected.timestamp(), delta=5
        )


def _mock_qs(count=3):
    qs = MagicMock()
    qs.count.return_value = count
    return qs


# ---------------------------------------------------------------------------
# Handler: dry-run tests
# Patch models at their source so the local `from ... import X` picks up mocks.
# ---------------------------------------------------------------------------

class PurgeHandlerDryRunTests(TestCase):
    """Handlers must not delete anything during a dry run."""

    @override_settings(PII_RETENTION_DAYS=365)
    def test_pii_dry_run_does_not_delete(self):
        qs = _mock_qs(5)
        with patch("apps.candidates.models.Candidate") as MockCandidate:
            MockCandidate.objects.filter.return_value = qs
            count = _purge_pii(dry_run=True)
        qs.delete.assert_not_called()
        self.assertEqual(count, 5)

    @override_settings(BIOMETRIC_RETENTION_DAYS=180)
    def test_biometric_dry_run_does_not_update(self):
        qs = _mock_qs(2)
        with patch("apps.interviews.models.InterviewSession") as MockSession:
            MockSession.objects.filter.return_value = qs
            count = _purge_biometric(dry_run=True)
        qs.update.assert_not_called()
        self.assertEqual(count, 2)

    @override_settings(BACKGROUND_CHECK_RETENTION_DAYS=365)
    def test_background_check_dry_run_does_not_delete(self):
        qs = _mock_qs(4)
        with patch("apps.background_checks.models.BackgroundCheck") as MockBC:
            MockBC.objects.filter.return_value = qs
            count = _purge_background_checks(dry_run=True)
        qs.delete.assert_not_called()
        self.assertEqual(count, 4)

    @override_settings(AUDIT_LOG_RETENTION_DAYS=730)
    def test_audit_log_dry_run_does_not_delete(self):
        qs = _mock_qs(10)
        with patch("apps.audit.models.AuditLog") as MockLog:
            MockLog.objects.filter.return_value = qs
            count = _purge_audit_logs(dry_run=True)
        qs.delete.assert_not_called()
        self.assertEqual(count, 10)


class PurgeHandlerLiveTests(TestCase):
    """Handlers must call delete/update when dry_run=False and records exist."""

    @override_settings(PII_RETENTION_DAYS=365)
    def test_pii_live_run_calls_delete(self):
        qs = _mock_qs(3)
        with patch("apps.candidates.models.Candidate") as MockCandidate:
            MockCandidate.objects.filter.return_value = qs
            _purge_pii(dry_run=False)
        qs.delete.assert_called_once()

    @override_settings(BIOMETRIC_RETENTION_DAYS=180)
    def test_biometric_live_run_calls_update(self):
        qs = _mock_qs(1)
        with patch("apps.interviews.models.InterviewSession") as MockSession:
            MockSession.objects.filter.return_value = qs
            _purge_biometric(dry_run=False)
        qs.update.assert_called_once_with(recording_url=None, transcript=None)

    @override_settings(BACKGROUND_CHECK_RETENTION_DAYS=365)
    def test_background_check_live_run_calls_delete(self):
        qs = _mock_qs(2)
        with patch("apps.background_checks.models.BackgroundCheck") as MockBC:
            MockBC.objects.filter.return_value = qs
            _purge_background_checks(dry_run=False)
        qs.delete.assert_called_once()

    @override_settings(AUDIT_LOG_RETENTION_DAYS=730)
    def test_audit_log_live_run_calls_delete(self):
        qs = _mock_qs(7)
        with patch("apps.audit.models.AuditLog") as MockLog:
            MockLog.objects.filter.return_value = qs
            _purge_audit_logs(dry_run=False)
        qs.delete.assert_called_once()

    @override_settings(PII_RETENTION_DAYS=365)
    def test_zero_records_does_not_call_delete(self):
        qs = _mock_qs(0)
        with patch("apps.candidates.models.Candidate") as MockCandidate:
            MockCandidate.objects.filter.return_value = qs
            count = _purge_pii(dry_run=False)
        qs.delete.assert_not_called()
        self.assertEqual(count, 0)


class PurgeHandlerErrorHandlingTests(TestCase):
    """Handlers must not raise — errors are logged and return 0."""

    @override_settings(PII_RETENTION_DAYS=365)
    def test_pii_handler_catches_exception(self):
        with patch("apps.candidates.models.Candidate") as MockCandidate:
            MockCandidate.objects.filter.side_effect = Exception("db error")
            count = _purge_pii(dry_run=False)
        self.assertEqual(count, 0)

    @override_settings(AUDIT_LOG_RETENTION_DAYS=730)
    def test_audit_handler_catches_exception(self):
        with patch("apps.audit.models.AuditLog") as MockLog:
            MockLog.objects.filter.side_effect = Exception("db unavailable")
            count = _purge_audit_logs(dry_run=False)
        self.assertEqual(count, 0)


class PurgeCommandTests(TestCase):
    def _fake_handlers(self, counts: dict):
        """Build a _SCOPE_HANDLERS replacement with MagicMock handlers returning given counts."""
        from apps.core.management.commands.purge_expired_data import _SCOPE_HANDLERS
        return {
            scope: MagicMock(return_value=counts.get(scope, 0))
            for scope in _SCOPE_HANDLERS
        }

    def _run_command(self, handlers, **kwargs):
        cmd = Command()
        cmd.stdout = StringIO()
        cmd.stderr = StringIO()
        cmd.style = MagicMock()
        cmd.style.SUCCESS = lambda x: x
        cmd.style.WARNING = lambda x: x
        options = {"dry_run": False, "scope": ALL_SCOPES, **kwargs}
        with patch("apps.core.management.commands.purge_expired_data._SCOPE_HANDLERS", handlers):
            cmd.handle(**options)
        return cmd.stdout.getvalue()

    def test_command_reports_total_purged(self):
        handlers = self._fake_handlers({
            SCOPE_PII: 2,
            SCOPE_BIOMETRIC: 1,
            SCOPE_BACKGROUND_CHECKS: 0,
            SCOPE_AUDIT_LOGS: 3,
        })
        output = self._run_command(handlers)
        # 2 + 1 + 0 + 3 = 6
        self.assertIn("6", output)

    def test_command_dry_run_prints_warning(self):
        handlers = self._fake_handlers({})
        cmd = Command()
        cmd.stdout = StringIO()
        cmd.stderr = StringIO()
        mock_style = MagicMock()
        mock_style.SUCCESS = lambda x: x
        mock_style.WARNING = MagicMock(return_value="[WARNING] dry run")
        cmd.style = mock_style

        with patch("apps.core.management.commands.purge_expired_data._SCOPE_HANDLERS", handlers):
            cmd.handle(dry_run=True, scope=ALL_SCOPES)

        mock_style.WARNING.assert_called()

    def test_command_runs_only_requested_scopes(self):
        mock_pii = MagicMock(return_value=1)
        mock_audit = MagicMock(return_value=0)
        handlers = {
            SCOPE_PII: mock_pii,
            SCOPE_BIOMETRIC: MagicMock(return_value=0),
            SCOPE_BACKGROUND_CHECKS: MagicMock(return_value=0),
            SCOPE_AUDIT_LOGS: mock_audit,
        }
        cmd = Command()
        cmd.stdout = StringIO()
        cmd.stderr = StringIO()
        cmd.style = MagicMock()
        cmd.style.SUCCESS = lambda x: x

        with patch("apps.core.management.commands.purge_expired_data._SCOPE_HANDLERS", handlers):
            cmd.handle(dry_run=False, scope=[SCOPE_PII])

        mock_pii.assert_called_once_with(dry_run=False)
        mock_audit.assert_not_called()
