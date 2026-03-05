# Defense Interruption Q&A (15-Second Answers)

Use these when the panel interrupts your flow mid-slide.

## 1) "Is this really production-ready?"

- "It is production-oriented and functionally complete as an MVP. Launch is gated only by the remaining deployment hardening controls listed in the readiness scorecard."

## 2) "Why should we trust AI decisions?"

- "The system does not auto-finalize high-risk uncertainty. Low-confidence outputs are escalated to manual review, and final decisions stay human-owned."

## 3) "What if your model is wrong?"

- "Every model output is stored with evidence and confidence. HR can override, and the audit trail records the reason and actor for governance."

## 4) "How do you handle external API failure?"

- "Provider calls are isolated from request paths via async workers, retried with backoff, and surfaced as pending/degraded states rather than silent failure."

## 5) "What happens if webhooks are missed?"

- "Subscription/background states can be reconciled through explicit confirmation paths, so state can recover without manual DB edits."

## 6) "Can users bypass plan limits?"

- "No. Quotas are enforced server-side on write paths, not only in frontend UX."

## 7) "Why Django + Celery instead of microservices?"

- "Single-backend modular architecture reduced integration risk for this phase while preserving service boundaries for future extraction if needed."

## 8) "How do you protect sensitive data?"

- "Role boundaries, 2FA for non-candidate accounts, retention policies, and audit logging are enforced. Production secret management is part of the remaining P0 hardening."

## 9) "What if Redis/Celery is down?"

- "The API still serves non-async operations, and async jobs pause rather than corrupting transactional state. Health status makes this visible immediately."

## 10) "How do you prove quality?"

- "Through automated gates: backend/frontend tests, lint/type checks, API schema checks, endpoint coverage, and deploy safety checks."

## 11) "Why both Stripe and Paystack?"

- "Coverage and payment-channel flexibility. Stripe handles card-first global flows; Paystack supports regional rails, including mobile-money scenarios."

## 12) "Can this scale beyond one company?"

- "Yes. The data model and role-based flows are workspace-oriented, and async processing allows horizontal scaling of worker capacity."

## 13) "What is your biggest technical debt?"

- "Operational hardening: secrets manager rollout, production webhook hardening completion, and expanded incident runbooks."

## 14) "What would you do in the next two weeks?"

- "Close P0 hardening items, execute full release gate in production-like infra, and run a staged go-live with monitoring and rollback plan."

## 15) "If the live demo fails now?"

- "I will switch to seeded deterministic data to show full workflow behavior and audit outputs without relying on external provider uptime."
