# Defense Slide Deck Outline

## Slide 1: Title + Problem Statement (45s)

- Title: `AI-Powered Vetting System for HR Screening`
- Subtitle: `Production-Oriented MVP with Human-in-the-Loop AI`
- Problem:
  - Manual vetting is slow.
  - Results can be inconsistent across reviewers.
  - Auditability is weak in traditional workflows.

Speaker note:

- "This project automates vetting while preserving human decision authority."

## Slide 2: Objectives and Scope (45s)

- Objectives:
  - Automate document and interview vetting.
  - Standardize scoring via rubric-based evaluation.
  - Provide auditable decision trails.
- Scope:
  - Campaign orchestration
  - Candidate enrollment/invitations
  - AI analysis pipeline
  - Billing and quota enforcement

## Slide 3: System Architecture (75s)

- Show diagram from `DEFENSE_ARCHITECTURE_ONE_PAGER.md`.
- Components:
  - Frontend (React/TS)
  - Backend (Django/DRF)
  - Async runtime (Celery/Redis)
  - Data layer (PostgreSQL + artifacts)
  - Providers (Stripe, Paystack, LiveKit, background-check API)

Speaker note:

- "Heavy AI and notification workloads run asynchronously, keeping API response times stable."

## Slide 4: End-to-End Workflow (75s)

- Sequence:
  - HR creates campaign + rubric.
  - Candidates are enrolled/imported and invited.
  - Document/interview analysis tasks run in queue.
  - AI scores and flags are returned.
  - HR/Admin performs final decision.

Speaker note:

- "AI recommends; human approves/rejects/escalates."

## Slide 5: AI/ML Pipeline Design (75s)

- Modalities:
  - OCR/document authenticity/fraud signals
  - Interview/transcript and behavior analysis
- Governance:
  - Confidence thresholds
  - Manual review routing for uncertain cases
  - Persisted evidence trail for explainability

## Slide 6: Security, Roles, and Trust Boundaries (60s)

- Controls:
  - Role-based access (admin/hr/candidate)
  - 2FA path for non-candidate accounts
  - CSRF/CORS + token/session controls
  - Audit logs and retention policies

Speaker note:

- "Security is applied at boundary points: browser->API, API->workers, API->providers."

## Slide 7: Billing and Quota Enforcement (60s)

- Providers:
  - Stripe and Paystack support
- Features:
  - Subscription lifecycle and confirmations
  - Plan-based monthly quota enforcement at backend level
  - Retry/reconciliation paths for payment failures

## Slide 8: Testing and Quality Gates (60s)

- Evidence:
  - Backend and frontend test suites
  - Lint/type-check/build gates
  - API schema checks and endpoint coverage
  - Deploy checks for production setting safety

Speaker note:

- "Release quality is driven by enforceable CI gates, not manual assumptions."

## Slide 9: Readiness and Risks (60s)

- Current position:
  - Strong production-oriented MVP readiness
- Remaining launch blockers (P0):
  - Production origin/env hardening
  - Webhook hardening completion
  - Secrets manager rollout
- Risk handling:
  - Retry/backoff
  - Pending-state reconciliation
  - Manual review fallback

## Slide 10: Conclusion + Next Steps (45s)

- Conclusion:
  - Core workflow and architecture are complete and defensible.
  - Remaining work is deployment hardening and ops maturity.
- Next steps:
  - Complete P0 controls
  - Run full launch gate in production-like environment
  - Roll out with monitored staging->production promotion

## Optional Appendix A: Demo Script (5 minutes)

1. Login as HR/admin.
2. Create campaign + rubric.
3. Import/enroll candidate.
4. Show analysis status and case decision path.
5. Show billing/subscription page and quota-relevant UX.

## Optional Appendix B: Panel Q&A

- Use Q&A section from `LAUNCH_READINESS_SCORECARD_2026-03-05.md`.

## Companion Script

- Verbatim talk track: `DEFENSE_7_MINUTE_SCRIPT.md`
- Interruption quick answers: `DEFENSE_INTERRUPTION_QA.md`
