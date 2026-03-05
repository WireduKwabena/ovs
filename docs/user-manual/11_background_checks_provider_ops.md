# 11) Background Checks and Provider Integration

## 11.1 Background Check Scope

OVS supports background checks as a managed subsystem with provider abstraction.

Key routes:

- Frontend: `/background-checks`
- APIs:
  - `GET/POST /api/background-checks/checks/`
  - `GET/PATCH/DELETE /api/background-checks/checks/{id}/`
  - `GET /api/background-checks/checks/{id}/events/`
  - `POST /api/background-checks/checks/{id}/refresh/`
  - `POST /api/background-checks/providers/{provider_key}/webhook/`

## 11.2 Provider Modes

Typical provider mode values:

- `mock` (development/testing only),
- `http` (real external provider integration).

Production recommendation:

- Use real provider mode and enforce webhook/token security.

## 11.3 Consent and Governance

Background check operations should require:

- explicit candidate consent records,
- traceable run metadata,
- status progression with reviewability.

## 11.4 Refresh and Event Flow

1. Create or trigger check.
2. Provider submission occurs.
3. Events and status updates are tracked.
4. Refresh endpoint can pull latest provider status.
5. Webhooks update state asynchronously.

## 11.5 Webhook Security Practices

1. Validate provider-specific signatures or auth headers.
2. Keep webhook secret/token in secured environment variables.
3. Ensure idempotency when processing repeated events.
4. Log every webhook payload metadata for forensics.

## 11.6 Operator Checklist

Before enabling production background checks:

1. Set provider base URL.
2. Set provider API key.
3. Set webhook token/secret.
4. Validate webhook endpoint reachability.
5. Test submit -> refresh -> final status path.

## 11.7 Common Background Check Issues

- Provider returns partial data: treat as pending, not final fail.
- Webhook not received: use refresh endpoint and provider logs.
- Unexpected status mapping: verify provider adapter and normalization logic.

