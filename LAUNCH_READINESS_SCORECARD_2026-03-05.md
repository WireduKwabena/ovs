# Launch Readiness Scorecard (2026-03-05)

## Overall Score

- `9.3 / 10` (strong pre-production state; a few P0 controls still required before go-live)

## Evidence (executed 2026-03-05)

- Backend tests: `360/360` passed.
- Frontend tests: `91/91` passed.
- Frontend lint: passed.
- Frontend type-check: passed.
- Frontend CI build + bundle budgets: passed.
- Frontend OpenAPI endpoint coverage: `100%` (after parser fix to include `publicApi.*` calls).
- Django deploy checks (`check --deploy`) now pass clean with production-safe CI overrides.

## P0 (Must-Fix Before Production)

1. Production env/origin hardening must be fully set in deploy env.
   - Evidence: `manage.py check --deploy --settings=config.settings.production` failed in current container due to local origin:
     - `CSRF_TRUSTED_ORIGINS entry must use https:// in production: http://localhost:3000`
   - Action:
     - Set production-only HTTPS values for `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`, `DJANGO_API_URL`.

2. Background-check provider must be real provider (not mock) at deployment.
   - Production settings already enforce this.
   - Action:
     - Set `BACKGROUND_CHECK_DEFAULT_PROVIDER=http`
     - Set `BACKGROUND_CHECK_WEBHOOK_TOKEN`, `BACKGROUND_CHECK_HTTP_BASE_URL`, `BACKGROUND_CHECK_HTTP_API_KEY`.
     - Validate provider webhook signature path end-to-end.

3. Payment webhook production setup must be completed for both Stripe and Paystack.
   - Action:
     - Stripe: configure webhook endpoint + `STRIPE_WEBHOOK_SECRET`.
     - Paystack: configure callback/webhook endpoint and secret validation path.
     - Verify subscription state transitions (`open -> active`, cancellation at period end, retry path).

4. Secrets handling must use a managed store in production.
   - Action:
     - Move keys/tokens from static env files into secret manager or CI/CD secret vault.
     - Rotate values after first production bootstrap.

## P1 (Should Complete Within 1 Week of Launch Prep)

1. Add formal backup/restore runbook (DB + media + model artifacts) with recovery RTO/RPO.
2. Add incident/runbook docs for:
   - billing webhook failure
   - Celery backlog growth
   - model quality gate failure (manifest/metric gates).
3. Add alert thresholds to ops dashboards:
   - queue depth, task retry exhaustions, payment confirmation lag, reminder runtime unavailable.
4. Pin and periodically review third-party dependency security updates.

## P2 (Post-Launch Hardening)

1. WAF/rate-limit policy at edge (beyond app-level middleware).
2. Optional data encryption posture uplift:
   - per-field encryption for high-sensitivity PII.
3. Chaos/load drills for:
   - provider outage
   - Redis failover
   - sustained interview/video-call peak traffic.

## Changes Made During This Pass

- Removed stray hashed credential artifact from `.env.prod.example`.
- Added missing production template variables in `.env.prod.example`:
  - background-check provider/token/http settings
  - service token
  - Stripe billing portal return URL
- Fixed potentially unsafe inline env comment in `backend/.env.example`:
  - `BACKGROUND_CHECK_DEFAULT_PROVIDER` now clean value + explanatory comment line.
- Fixed frontend endpoint coverage parser to include `publicApi.*` calls:
  - `frontend/scripts/check-endpoint-coverage.mjs`
- Added strict CI release gate workflow:
  - `.github/workflows/release-gate.yml`
  - Enforces frontend gates, backend full tests, and production deploy checks.
  - Includes OpenAPI schema validation + drift detection.
  - Publishes CI artifacts (frontend dist, backend test/deploy/openapi logs, generated schema) for PR diagnostics.
- Removed drf_spectacular warning sources:
  - Added explicit health response schema for `SystemHealthAPIView`.
  - Added explicit enum override sources for `scope` choice sets.
  - Added type hints on authentication profile serializer method fields.
- Regenerated and synchronized committed schema artifact:
  - `backend/openapi.yaml`
- Added schema contract test coverage:
  - `backend/apps/core/test_health.py` now asserts `/api/system/health/` references `SystemHealthResponse` and required fields.

## Recommended Release Gate Command Set

1. `docker compose exec backend python manage.py test --keepdb`
2. `npm --prefix frontend run test`
3. `npm --prefix frontend run lint`
4. `npm --prefix frontend run type-check`
5. `npm --prefix frontend run build:ci`
6. `npm --prefix frontend run coverage:endpoints -- --strict`
7. `docker compose exec backend python manage.py check --deploy --settings=config.settings.production`

## Go/No-Go Checklist (Defense + Launch)

- `GO` only if all P0 items are complete and re-verified in a production-like environment.
- `GO` only if release gate commands all pass in one CI run artifact bundle.
- `GO` only if webhook callbacks (Stripe + Paystack + background-check provider) are tested end-to-end.
- `NO-GO` if `check --deploy` fails for production settings.
- `NO-GO` if quota enforcement is bypassable from direct API calls.

## Defense Readiness Rating

- Technical implementation readiness: `9.3 / 10`
- Defense narrative readiness: `9.0 / 10`
- Launch execution readiness (current): `8.6 / 10` (blocked by remaining P0 deployment controls)

## 7-Minute Defense Talk Track

1. Problem framing (45s)
   - Manual vetting is slow, inconsistent, and difficult to audit.
   - This platform automates campaign-based vetting with AI-assisted document/interview analysis and human review controls.

2. Architecture (90s)
   - Django API handles orchestration, tenancy/workspace behavior, RBAC, and audit logging.
   - Celery + Redis execute heavy asynchronous jobs (AI analysis, notifications, reminders, provider polling).
   - Frontend React app provides role-based workflow UIs (admin, HR manager, candidate access flow).
   - Billing enforces subscription and quotas with provider-backed payment confirmation.

3. Core workflow demo summary (90s)
   - Create campaign -> configure rubric -> register/import candidates.
   - Candidate receives access link and submits required vetting artifacts.
   - AI services score evidence; low-confidence paths route to manual review.
   - HR/admin gets consolidated case view and final decision actions.

4. Engineering quality controls (90s)
   - Test suite status: backend and frontend passing.
   - API schema and coverage checks wired in CI.
   - Production checks (`check --deploy`) and config safety guards.
   - Background-check and billing integration points with webhook event handling.

5. Security and governance (60s)
   - Role restrictions, 2FA path for non-candidate accounts, CSRF/CORS constraints.
   - Retention controls and audit trails for operational accountability.
   - Environment-aware behavior (debug vs production email, provider constraints).

6. Known limitations and immediate next actions (45s)
   - Finalize P0 deployment environment settings and secrets management.
   - Complete external provider webhook hardening in production infra.
   - Complete runbook/alerts for operational response.

7. Closing (20s)
   - Project is a production-oriented MVP with strong architecture and verified gates.
   - Remaining work is deployment hardening, not core feature feasibility.

## Panel Q&A Cheat Sheet

- Q: "Is it production-ready now?"
  - A: "Core product behavior is ready; launch readiness is gated by P0 deployment controls listed here."
- Q: "How do you prevent AI latency from blocking users?"
  - A: "Inference and long-running checks are asynchronous via Celery workers; API remains responsive."
- Q: "How are false positives handled?"
  - A: "Threshold routing pushes ambiguous/low-confidence cases to manual review instead of auto-fail."
- Q: "How do you enforce subscriptions?"
  - A: "Quota checks are backend enforced; direct API calls cannot bypass plan limits."
- Q: "What if payment webhooks fail?"
  - A: "State remains pending/open and can be reconciled by explicit provider confirmation endpoints and retries."
- Q: "What if provider APIs are unavailable?"
  - A: "Jobs are retried with backoff; status surfaces in runtime health and audit logs."

## Defense Demo Safety Checklist (Do This Before Presentation)

1. Seed one admin, one HR manager, one candidate scenario with predictable data.
2. Verify all provider keys in demo env are test-mode keys.
3. Keep one pre-completed case in DB as fallback if live provider call fails.
4. Validate `docker compose ps` health is green for db/backend/celery/flower.
5. Pre-open logs for backend + worker in separate terminals for transparency.

## Companion Defense Artifact

- Defense pack index (single entry): `DEFENSE_PACK.md`
- Architecture one-pager: `DEFENSE_ARCHITECTURE_ONE_PAGER.md`
- Slide deck outline: `DEFENSE_SLIDE_DECK_OUTLINE.md`
- Verbatim 7-minute script: `DEFENSE_7_MINUTE_SCRIPT.md`
- Executive summary (2-minute): `DEFENSE_2_MINUTE_EXEC_SUMMARY.md`
- Interruption Q&A (15-second answers): `DEFENSE_INTERRUPTION_QA.md`
- Question-to-slide jump map: `DEFENSE_QUESTION_TO_SLIDE_MAP.md`
- Mock panel drill (20 questions): `DEFENSE_MOCK_PANEL_DRILL.md`
- Night-before runbook: `NIGHT_BEFORE_DEFENSE_CHECKLIST.md`
