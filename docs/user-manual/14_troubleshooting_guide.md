# 14) Troubleshooting Guide

## 14.1 Login and Auth Problems

### Symptom: "CSRF token missing" or origin check failed

Actions:

1. Confirm frontend origin is in `CSRF_TRUSTED_ORIGINS`.
2. Confirm frontend origin is in `CORS_ALLOWED_ORIGINS`.
3. Restart backend after env changes.
4. Clear stale browser cookies/session and retry.

### Symptom: Login succeeds but redirects incorrectly

Actions:

1. Confirm user role in profile payload.
2. Confirm route guard logic has expected user type.
3. Verify profile fetch completes after login.

## 14.2 Billing/Checkout Problems

### Symptom: `/billing/success` hangs on "Confirming Payment"

Actions:

1. Confirm success URL contains session/reference parameter.
2. Check browser network for confirm endpoint call.
3. Call confirm endpoint manually for diagnosis.
4. Check backend billing logs and provider dashboard.

### Symptom: "Transaction reference not found"

Actions:

1. Use exact reference returned by latest checkout session.
2. Ensure confirm call matches the provider (Stripe vs Paystack).
3. Ensure backend env keys target same provider account mode.

## 14.3 Reminder Runtime Unavailable

### Symptom: reminder runtime card shows unavailable or fetch error

Actions:

1. Confirm backend and Celery services are healthy.
2. Confirm reminder endpoint permissions for current user.
3. Review worker logs for failed reminder jobs.
4. Verify Redis connectivity.

## 14.4 Candidate/Invitation Issues

### Symptom: candidate cannot access invite link

Actions:

1. Verify invitation token and expiry state.
2. Re-send invitation from invitation endpoint.
3. Confirm candidate access consume endpoint works.
4. Check candidate enrollment status.

## 14.5 Video Call Join Issues

### Symptom: cannot join meeting

Actions:

1. Confirm meeting is started or joinable.
2. Verify join-token endpoint response.
3. Verify LiveKit env configuration.
4. Check network/firewall restrictions for realtime transport.

## 14.6 Background Check Stuck in Pending

Actions:

1. Trigger refresh endpoint.
2. Confirm provider API credentials and base URL.
3. Verify webhook path and token/secret validation.
4. Inspect provider-side event logs.

## 14.7 AI Monitoring Endpoints Not Accessible

Actions:

1. Confirm account is admin/staff where required.
2. Confirm service token paths are configured as intended.
3. Validate endpoint path and auth headers.

## 14.8 Docker Build/Startup Issues

### Symptom: image build fails or service unhealthy

Actions:

1. Ensure `.dockerignore` excludes local virtual env and large datasets.
2. Rebuild with no cache if dependency corruption suspected:

```powershell
docker compose build --no-cache
```

3. Start stack and inspect health:

```powershell
docker compose up -d
docker compose ps
docker compose logs -f backend
```

## 14.9 Last-Resort Incident Procedure

1. Freeze user-facing writes if data integrity risk is suspected.
2. Collect logs from backend, worker, and provider callbacks.
3. Capture failing request/response payload metadata.
4. Reproduce issue in controlled environment.
5. Apply fix and verify with targeted test.

