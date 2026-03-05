# 16) Glossary and Best Practices

## 16.1 Glossary

- Campaign: A vetting process container with rules, candidates, and timeline.
- Rubric: Weighted scoring template used to evaluate case evidence.
- Enrollment: Candidate linkage to a specific campaign.
- Invitation: Tokenized candidate onboarding entry.
- Case/Application: Candidate evidence package for review.
- Verification status: Current state of analysis and review for a case.
- Manual review: Human-required decision path for uncertain AI outputs.
- Subscription ticket/access verification: Billing-linked authorization to register or continue service.
- Reminder runtime: Scheduler/worker state for meeting reminders and notifications.
- Provider webhook: External callback notifying payment/background check status updates.
- Reconciliation: Explicit status refresh/confirm call to recover missed callback events.

## 16.2 User Best Practices

### For HR Managers

1. Activate rubric before importing candidates.
2. Validate data quality during import.
3. Review low-confidence cases manually.
4. Keep campaign notes and decision rationale consistent.

### For Admins

1. Limit admin accounts and enforce 2FA.
2. Review audit logs routinely.
3. Track operational metrics for backlog/failure trends.
4. Separate policy controls from day-to-day vetting execution.

### For Candidates

1. Use valid invitation links only.
2. Submit clear and complete documents.
3. Complete interview steps within provided window.
4. Keep personal information accurate.

## 16.3 Operational Best Practices

1. Run full release gate before major deployments.
2. Use production-safe env configuration and secret management.
3. Keep logs available during critical operations and demos.
4. Test provider callbacks in staging before production rollout.
5. Maintain one deterministic fallback case for demos/training.

## 16.4 Security Best Practices

1. Do not commit secrets or API keys into source control.
2. Rotate exposed credentials immediately.
3. Keep CSRF/CORS origins explicit and least-privileged.
4. Restrict service-token usage to service-to-service contexts only.
5. Treat billing and background-check webhooks as high-integrity entry points.

## 16.5 Decision Governance Best Practices

1. Use AI as decision support, not absolute authority.
2. Preserve criterion-level evidence on every major decision.
3. Require manual review for conflicts or low-confidence outputs.
4. Log overrides with justification and reviewer identity.
5. Maintain clear retention and archival policies.

## 16.6 Manual Maintenance Policy

To keep this manual accurate:

1. Update route references whenever `frontend/src/App.tsx` changes.
2. Update endpoint map whenever `backend/openapi.yaml` changes.
3. Review role behavior whenever auth or permissions are modified.
4. Review billing and provider sections whenever integrations change.
5. Version user manual updates alongside release tags.

