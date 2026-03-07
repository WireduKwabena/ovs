# 10) Monitoring, Audit Logs, and AI Runtime Health

## 10.1 Monitoring Surfaces

Frontend pages:

- `/audit-logs` (admin only)
- `/ml-monitoring` (admin only)
- `/ai-monitor` (admin only)

Backend health route:

- `/api/system/health/`

## 10.2 Audit Endpoints

- `GET /api/audit/logs/`
- `GET /api/audit/logs/{id}/`
- `GET /api/audit/logs/by_entity/`
- `GET /api/audit/logs/recent_activity/`
- `GET /api/audit/logs/statistics/`

## 10.3 ML Monitoring Endpoints

- `GET /api/ml-monitoring/`
- `GET /api/ml-monitoring/{id}/`
- `GET /api/ml-monitoring/latest/`
- `GET /api/ml-monitoring/history/`
- `GET /api/ml-monitoring/performance-summary/`

Legacy aliases under `/api/ml-monitoring/metrics/` are also supported.

## 10.4 AI Monitor Endpoints

- `GET /api/ai-monitor/health/`
- `POST /api/ai-monitor/classify-document/`
- `POST /api/ai-monitor/check-social-profiles/`

## 10.5 Runtime Health Signals

Track:

- Request latency and error rates,
- Celery queue backlog and retry volume,
- Background check refresh failures,
- Billing confirmation lag,
- Video call reminder runtime availability.

## 10.6 Audit Usage Pattern

Use audit for:

1. Investigating disputed decisions.
2. Tracking high-risk role changes.
3. Reconstructing operational incidents.
4. Compliance and reporting evidence.

Government workflow events include appointment and decision-support contracts such as:

- `appointment_nomination_created`
- `appointment_stage_transition`
- `appointment_stage_action_taken`
- `appointment_final_decision_recorded`
- `appointment_publication_published`
- `appointment_publication_revoked`
- `vetting_decision_recommendation_generated`
- `vetting_decision_override_recorded`

## 10.7 Monitoring Best Practices

1. Monitor trends, not only snapshots.
2. Alert on deviation thresholds.
3. Correlate user-facing incidents with task/runtime logs.
4. Keep service tokens and admin-only metrics endpoints protected.

## 10.8 Troubleshooting "Unavailable Runtime" Indicators

If runtime cards show unavailable:

1. Confirm backend health endpoint status.
2. Confirm Redis and Celery services are running.
3. Check endpoint-specific auth/permission context.
4. Inspect backend and worker logs for recent errors.
