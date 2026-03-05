# Defense 7-Minute Script (Verbatim)

## Slide 1: Title + Problem (0:00 - 0:45)

"Good day. My project is an AI-powered vetting system for HR screening.  
The core problem I addressed is that manual vetting is slow, inconsistent, and difficult to audit at scale.  
Different reviewers can reach different conclusions for similar candidates, and organizations struggle to maintain a clear evidence trail for decisions.  
This system introduces structured, campaign-based vetting with AI assistance and human oversight, so decisions are faster, more consistent, and traceable."

## Slide 2: Objectives and Scope (0:45 - 1:30)

"The project has three main objectives.  
First, automate document and interview vetting workflows.  
Second, standardize scoring using configurable rubrics and thresholds.  
Third, preserve decision accountability through auditability and human final approval.  
The implemented scope includes campaign orchestration, candidate enrollment and invitation flows, AI analysis pipelines, billing and subscription control, and role-based access flows for Admin, HR Manager, and Candidate."

## Slide 3: Architecture (1:30 - 2:45)

"Architecturally, the system is split into clear layers.  
The frontend is React with TypeScript for role-based user interfaces.  
The backend is Django REST Framework, which handles business rules, RBAC, orchestration, billing logic, and audit records.  
Heavy operations run asynchronously using Celery with Redis as broker and cache.  
PostgreSQL stores transactional system state, and artifact storage handles uploaded files and model outputs.  
External providers include Stripe and Paystack for payments, LiveKit for real-time interview communication, and a background-check provider integration path.  
The key design decision is asynchronous execution: expensive AI and provider tasks never block request-response API performance."

## Slide 4: End-to-End Workflow (2:45 - 4:00)

"A typical flow starts with HR creating a campaign and attaching a rubric.  
Candidates are imported or enrolled, and invitations are issued.  
Candidates submit required evidence through guided flows.  
Document and interview analyses are queued and processed by workers.  
Results are persisted as structured evidence, scores, and flags.  
The dashboard aggregates these outputs for HR and Admin review.  
At the end, the final decision is human-owned: approve, reject, or escalate.  
This keeps the system practical for operations while maintaining accountability and compliance posture."

## Slide 5: AI/ML Pipeline (4:00 - 5:00)

"The AI layer is multi-modal.  
For documents, the pipeline supports OCR extraction, authenticity checks, fraud-oriented signal extraction, and consistency analysis.  
For interview signals, the pipeline supports transcript and behavioral feature processing.  
Most importantly, AI does not operate as an unchecked black box.  
The system captures confidence-aware outputs and routes uncertain cases to manual review.  
This threshold-based escalation strategy reduces unsafe auto-decisions and improves reliability in real HR workflows."

## Slide 6: Security and Trust Boundaries (5:00 - 5:45)

"Security is applied at each trust boundary.  
At the application boundary, role-based permissions enforce separation between Admin, HR, and candidate access flows.  
2FA applies to non-candidate accounts.  
CSRF and CORS are environment-aware and constrained for deployment safety.  
At the operations boundary, asynchronous tasks are isolated and monitored.  
At the governance boundary, audit logs and retention policies preserve traceability and lifecycle control of sensitive data."

## Slide 7: Billing and Quotas (5:45 - 6:20)

"The system integrates both Stripe and Paystack.  
Billing state transitions are reflected in backend subscription records, and plan quotas are enforced server-side.  
That means limits are not just UI hints; direct API calls are also constrained.  
There are fallback and reconciliation paths for delayed or missed webhooks so subscription status can be safely confirmed without corrupting state."

## Slide 8: Quality Gates and Evidence (6:20 - 6:45)

"From an engineering quality perspective, the platform is guarded by automated checks: backend and frontend tests, linting, type checks, schema and endpoint coverage validation, and deploy-time settings checks.  
This creates a repeatable release gate and reduces configuration drift risk during deployment."

## Slide 9: Readiness and Risks (6:45 - 7:15)

"Current readiness is strong for a production-oriented MVP.  
The remaining high-priority items are deployment hardening tasks: strict production origin settings, complete webhook hardening in production infrastructure, and managed secret storage with rotation policy.  
These are operational readiness tasks, not core architecture or feasibility blockers."

## Slide 10: Close (7:15 - 7:30)

"In summary, this project delivers an end-to-end AI-assisted vetting platform with human-in-the-loop decision control, strong modular architecture, and practical operational design.  
The next step is final launch hardening.  
Thank you."

## Optional 20-Second Backup Close

"If live provider connectivity fails during demo, I will show the same workflow using pre-seeded completed cases and audit records to demonstrate system behavior deterministically."
