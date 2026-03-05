# Night-Before Defense Checklist (10 Minutes)

## 0) Objective

- Ensure the demo runs deterministically.
- Verify all critical services are healthy.
- Confirm fallback data is available if external providers fail live.

## 1) Environment Sanity (1 minute)

Run from project root:

```powershell
docker compose ps
```

Pass criteria:

- `db`, `redis`, `backend`, `celery_worker`, `celery_beat`, `flower` are running.

If failed:

- Restart stack:

```powershell
docker compose up -d --build
```

## 2) Backend Health + Settings (1 minute)

```powershell
docker compose exec backend python manage.py check --settings=config.settings.development
```

Pass criteria:

- `System check identified no issues`.

## 3) Critical Tests Smoke (2 minutes)

```powershell
docker compose exec backend python manage.py test apps.billing.tests --keepdb
docker compose exec backend python manage.py test apps.campaigns.tests --keepdb
npm --prefix frontend run test -- --runInBand
```

Pass criteria:

- Billing + campaigns tests pass.
- Frontend test command exits successfully.

## 4) API and UI Build Gate (1 minute)

```powershell
npm --prefix frontend run lint
npm --prefix frontend run type-check
npm --prefix frontend run build
```

Pass criteria:

- All commands pass with zero blocking errors.

## 5) Demo Accounts + Access Check (1 minute)

Confirm you can log in to:

- Admin account
- HR manager account
- Candidate-access flow (token/session route)

If account issue appears:

- Reset password quickly:

```powershell
docker compose exec backend python manage.py changepassword <email_or_username>
```

## 6) Billing Demo Path Check (1 minute)

Validate both flows:

- Stripe test card flow (success page resolves and confirms).
- Paystack test flow (success callback confirms without hanging).

Verify latest subscription state:

```powershell
docker compose exec backend python manage.py shell -c "from apps.billing.models import BillingSubscription as S; x=S.objects.order_by('-created_at').first(); print(x.provider, x.status, x.payment_status, x.reference)"
```

## 7) Data Seeding Fallback (1 minute)

Keep one pre-completed candidate case in DB for offline fallback demo:

- Case has campaign, rubric, candidate, analysis result, final decision, audit logs.
- If provider/API live call fails, switch to this case and continue narrative.

## 8) Live Demo Tabs Prep (1 minute)

Open these tabs before presentation:

- Login page
- HR dashboard/campaign workspace
- Rubric page
- Case detail with analysis
- Billing/subscription page
- Admin audit/monitoring page

Keep these terminals open:

- `docker compose logs -f backend`
- `docker compose logs -f celery_worker`

## 9) Fallback Script (30 seconds)

If external provider fails mid-demo, say:

- "I’ll continue with the seeded deterministic case to demonstrate complete system behavior and auditability independent of provider uptime."

Then show:

- Completed case
- Evidence trail
- Decision + audit entries

## 10) Final Go/No-Go (30 seconds)

Go only if all are true:

- Services healthy
- Checks/tests pass
- Login works for admin + HR
- At least one completed fallback case exists
- Billing callback path confirms successfully in test mode

If any fails:

- Do not live-demo unstable flow; use fallback path for that segment.
