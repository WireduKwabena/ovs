# Defense Mock Panel Drill

Format per question:
- `Ideal answer`: concise, high-confidence response.
- `Avoid saying`: weak phrasing that lowers credibility.

## 1) What core problem does your project solve?
- Ideal answer: "It standardizes and accelerates vetting by combining campaign orchestration, AI-assisted evidence analysis, and human final decision control with full auditability."
- Avoid saying: "It does many things and automates everything."

## 2) Why is this not just a basic CRUD app?
- Ideal answer: "Core complexity is orchestration: async AI jobs, provider integrations, rubric-based scoring, quota enforcement, and role-restricted decision workflows."
- Avoid saying: "Because it has many pages."

## 3) Why did you choose Django + Celery?
- Ideal answer: "Django gives strong domain and permission modeling; Celery isolates heavy and failure-prone tasks so user-facing APIs remain responsive."
- Avoid saying: "That is what I know best."

## 4) How does your AI layer avoid unsafe decisions?
- Ideal answer: "Low-confidence or conflicting outputs route to manual review. AI recommends; humans approve, reject, or escalate."
- Avoid saying: "The model is always correct."

## 5) What evidence is stored for explainability?
- Ideal answer: "Per-case structured outputs include scores, confidence, flags, and metadata, linked to workflow state and final decision records."
- Avoid saying: "We only keep the final score."

## 6) What if external providers fail?
- Ideal answer: "Provider-dependent paths remain pending/open, retries are applied, and status is reconciled via explicit confirmation endpoints."
- Avoid saying: "Users should just retry later."

## 7) How do you handle missed webhooks?
- Ideal answer: "Webhook events are not the only source of truth. Confirmation endpoints reconcile provider transaction state safely."
- Avoid saying: "If webhook fails, payment is lost."

## 8) How are subscription limits enforced?
- Ideal answer: "Quota checks run server-side on protected write paths; frontend only reflects state and cannot bypass enforcement."
- Avoid saying: "Frontend disables buttons."

## 9) How do you secure user access?
- Ideal answer: "RBAC separates admin/hr/candidate permissions, non-candidate accounts use 2FA paths, and CSRF/CORS are environment-constrained."
- Avoid saying: "Only JWT handles security."

## 10) How do you protect sensitive data?
- Ideal answer: "Access is role-scoped, retention windows are defined, and high-risk actions are audit logged for traceability."
- Avoid saying: "We keep everything forever."

## 11) Is this production-ready now?
- Ideal answer: "It is production-oriented and functionally complete as an MVP; remaining blockers are deployment hardening controls already listed in P0."
- Avoid saying: "Yes, fully ready with no issues."

## 12) What are the current P0 blockers?
- Ideal answer: "Production origin/env hardening, webhook hardening completion, and managed secrets rollout."
- Avoid saying: "No blockers."

## 13) What is your biggest technical risk?
- Ideal answer: "Operational integration reliability across external providers, mitigated by retries, reconciliation paths, and fallback demo data."
- Avoid saying: "There is no risk."

## 14) How do you prove software quality?
- Ideal answer: "Through repeatable gates: tests, lint/type checks, API/schema checks, and deploy checks."
- Avoid saying: "I tested manually and it seemed fine."

## 15) How does your architecture scale?
- Ideal answer: "Async workers scale horizontally for analysis load while API nodes remain focused on orchestration."
- Avoid saying: "We can buy a bigger server."

## 16) Why both Stripe and Paystack?
- Ideal answer: "To support broader payment channels and regional flexibility while keeping one normalized subscription model."
- Avoid saying: "I added both because I could."

## 17) How do roles differ in practice?
- Ideal answer: "Admin governs platform-wide controls and oversight; HR manages campaign execution; candidates use constrained access flows."
- Avoid saying: "Roles are mostly the same."

## 18) What happens if AI runtime is unavailable?
- Ideal answer: "Core app remains operable; AI-dependent statuses degrade transparently and recover via task retries when runtime returns."
- Avoid saying: "System fully stops."

## 19) What would you do in the next sprint?
- Ideal answer: "Close P0 hardening, finalize runbooks/alerts, and run full release gate in production-like infra."
- Avoid saying: "Add more random features."

## 20) Why should this project pass?
- Ideal answer: "It solves a real workflow problem with a defensible architecture, measurable quality controls, and a realistic launch hardening plan."
- Avoid saying: "Because I worked hard on it."

## Rapid Practice Mode (5 Minutes)
1. Read questions 1, 4, 8, 11, 12, 14, 20 aloud.
2. Keep each answer under 15 seconds.
3. If an answer exceeds 20 seconds, tighten it to one claim + one proof.
