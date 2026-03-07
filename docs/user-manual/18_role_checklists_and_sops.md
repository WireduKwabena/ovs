# 18) Role Checklists and SOPs

## 18.1 Admin Daily Checklist

1. Verify service health and core metrics.
2. Review unread critical notifications.
3. Review audit anomalies and user-role changes.
4. Check billing/webhook error indicators.
5. Confirm no critical queue backlog.

## 18.2 Operations User Daily Checklist

1. Open campaign dashboard and review active workloads.
2. Confirm pending invitations and follow-ups.
3. Review flagged/low-confidence cases.
4. Confirm interview schedules and reminders.
5. Close decision loop with rationale notes.

## 18.3 Candidate Support Checklist

For support staff handling candidate issues:

1. Validate invitation token state.
2. Confirm candidate enrollment status.
3. Confirm document upload availability.
4. Confirm interview session accessibility.
5. Confirm results publication state.

## 18.4 Billing SOP

1. Verify current subscription status.
2. Verify payment method state.
3. If failed/pending:
   - trigger retry flow,
   - confirm provider status,
   - reconcile with confirm endpoint.
4. If cancellation requested:
   - schedule period-end cancellation,
   - communicate effective date.

## 18.5 Incident SOP: Provider Outage

1. Declare degraded mode and notify operators.
2. Keep candidate-facing workflows available where possible.
3. Queue or defer provider-dependent operations.
4. Use fallback deterministic case for demos/training.
5. Reconcile delayed operations once provider recovers.

## 18.6 Incident SOP: Authentication Failures

1. Verify CSRF/CORS origin configuration.
2. Verify 2FA status and challenge path.
3. Verify token/session freshness.
4. Check login history for suspicious patterns.

## 18.7 Incident SOP: Data Integrity Concern

1. Pause high-risk mutating operations if needed.
2. Collect logs, request IDs, and payload metadata.
3. Identify affected entities and scope.
4. Validate DB records against expected workflow states.
5. Apply controlled recovery and verify through tests.

## 18.8 Release-Day Checklist

1. Execute full release gate command sequence.
2. Confirm production env variables.
3. Validate webhook endpoints and secrets.
4. Confirm SMTP delivery path in production.
5. Confirm rollback plan and backup availability.

## 18.9 Defense/Demo-Day Checklist

1. Run service health checks.
2. Confirm admin and operations-user login paths.
3. Confirm one complete fallback case is available.
4. Keep backend and worker logs visible.
5. Follow `DEFENSE_PACK.md` order if interrupted.
