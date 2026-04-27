# 15) API Endpoint Quick Map

This is a quick operational map of the active backend API groups.  
Base prefixes:

- Preferred: `/api/v1/`
- Legacy compatibility: `/api/`

## 15.1 System and Core

- `/api/system/health/`

## 15.2 Authentication

- `/api/auth/register/`
- `/api/auth/login/`
- `/api/auth/logout/`
- `/api/auth/admin/login/`
- `/api/auth/login/verify/`
- `/api/auth/admin/login/verify/`
- `/api/auth/change-password/`
- `/api/auth/password-reset/`
- `/api/auth/password-reset-confirm/`
- `/api/auth/profile/`
- `/api/auth/profile/update/`
- `/api/auth/2fa/status/`
- `/api/auth/2fa/backup-codes/regenerate/`
- `/api/auth/admin/2fa/setup/`
- `/api/auth/admin/2fa/enable/`
- `/api/auth/token/refresh/` (optional when enabled)

## 15.3 Campaigns, Candidates, Enrollments, Invitations

- `/api/campaigns/`
- `/api/campaigns/{id}/`
- `/api/campaigns/{id}/candidates/import/`
- `/api/campaigns/{id}/dashboard/`
- `/api/campaigns/{id}/rubrics/versions/`
- `/api/campaigns/{id}/rubrics/versions/activate/`

- `/api/candidates/`
- `/api/candidates/{id}/`
- `/api/enrollments/`
- `/api/enrollments/{id}/`
- `/api/enrollments/{id}/mark-complete/`

- `/api/invitations/`
- `/api/invitations/{id}/`
- `/api/invitations/{id}/send/`
- `/api/invitations/accept/`
- `/api/invitations/access/consume/`
- `/api/invitations/access/me/`
- `/api/invitations/access/results/`
- `/api/invitations/access/logout/`

- `/api/social-profiles/`
- `/api/social-profiles/{id}/`

## 15.4 Applications and Documents

- `/api/applications/cases/`
- `/api/applications/cases/{id}/`
- `/api/applications/cases/{id}/upload-document/`
- `/api/applications/cases/{id}/verification-status/`
- `/api/applications/cases/{id}/recheck-social-profiles/`
- `/api/applications/documents/`
- `/api/applications/documents/{id}/`

## 15.5 Interviews and Video Calls

Interviews:

- `/api/interviews/interrogation/start/`
- `/api/interviews/upload-response/`
- `/api/interviews/sessions/`
- `/api/interviews/sessions/{id}/`
- `/api/interviews/sessions/{id}/start/`
- `/api/interviews/sessions/{id}/complete/`
- `/api/interviews/sessions/{id}/avatar-session/`
- `/api/interviews/sessions/{id}/playback/`
- `/api/interviews/sessions/{id}/save-exchange/`
- `/api/interviews/sessions/{id}/update-exchange/`
- `/api/interviews/sessions/analytics-dashboard/`
- `/api/interviews/sessions/compare/`
- `/api/interviews/sessions/generate-flags/`
- `/api/interviews/questions/`
- `/api/interviews/questions/{id}/`
- `/api/interviews/responses/`
- `/api/interviews/responses/{id}/`
- `/api/interviews/responses/{id}/analyze/`
- `/api/interviews/feedback/`
- `/api/interviews/feedback/{id}/`

Video calls:

- `/api/video-calls/meetings/`
- `/api/video-calls/meetings/{id}/`
- `/api/video-calls/meetings/upcoming/`
- `/api/video-calls/meetings/reminder-health/`
- `/api/video-calls/meetings/schedule-series/`
- `/api/video-calls/meetings/{id}/start/`
- `/api/video-calls/meetings/{id}/complete/`
- `/api/video-calls/meetings/{id}/cancel/`
- `/api/video-calls/meetings/{id}/reschedule/`
- `/api/video-calls/meetings/{id}/extend/`
- `/api/video-calls/meetings/{id}/leave/`
- `/api/video-calls/meetings/{id}/join-token/`
- `/api/video-calls/meetings/{id}/events/`
- `/api/video-calls/meetings/{id}/calendar-ics/`
- `/api/video-calls/meetings/{id}/cancel-series/`
- `/api/video-calls/meetings/{id}/reschedule-series/`

## 15.6 Rubrics and Scoring

- Rubric scoring endpoints:
- `/api/rubrics/vetting-rubrics/`
- `/api/rubrics/vetting-rubrics/{id}/`
- `/api/rubrics/vetting-rubrics/{id}/activate/`
- `/api/rubrics/vetting-rubrics/{id}/criteria/`
- `/api/rubrics/vetting-rubrics/{id}/duplicate/`
- `/api/rubrics/vetting-rubrics/{id}/evaluate-case/`
- `/api/rubrics/vetting-rubrics/{id}/evaluate_application/`
- `/api/rubrics/vetting-rubrics/create_from_template/`
- `/api/rubrics/vetting-rubrics/templates/`

- Evaluation + decision recommendation endpoints:
- `/api/rubrics/criteria/`
- `/api/rubrics/criteria/{id}/`
- `/api/rubrics/evaluations/`
- `/api/rubrics/evaluations/{id}/`
- `/api/rubrics/evaluations/{id}/rerun/`
- `/api/rubrics/evaluations/{id}/decision-recommendation/`
- `/api/rubrics/evaluations/{id}/override-decision/`
- `/api/rubrics/evaluations/{id}/override-criterion/`

## 15.7 Notifications, Audit, Fraud, Monitoring

Notifications:

- `/api/notifications/`
- `/api/notifications/{id}/`
- `/api/notifications/{id}/mark_read/`
- `/api/notifications/{id}/archive/`
- `/api/notifications/{id}/restore/`
- `/api/notifications/mark-as-read/`
- `/api/notifications/mark-all-as-read/`
- `/api/notifications/unread-count/`

Audit:

- `/api/audit/logs/`
- `/api/audit/logs/{id}/`
- `/api/audit/logs/by_entity/`
- `/api/audit/logs/by_user/`
- `/api/audit/logs/recent_activity/`
- `/api/audit/logs/statistics/`
- `/api/audit/logs/event_catalog/`

Fraud:

- `/api/fraud/results/`
- `/api/fraud/results/{id}/`
- `/api/fraud/results/statistics/`
- `/api/fraud/consistency/`
- `/api/fraud/consistency/{id}/`
- `/api/fraud/consistency/history/`
- `/api/fraud/consistency/statistics/`
- `/api/fraud/social-profiles/`
- `/api/fraud/social-profiles/{id}/`
- `/api/fraud/social-profiles/statistics/`

ML Monitoring:

- `/api/ml-monitoring/`
- `/api/ml-monitoring/{id}/`
- `/api/ml-monitoring/latest/`
- `/api/ml-monitoring/history/`
- `/api/ml-monitoring/performance-summary/`
- Legacy alias group: `/api/ml-monitoring/metrics/...`

AI Monitor:

- `/api/ai-monitor/health/`
- `/api/ai-monitor/classify-document/`
- `/api/ai-monitor/check-social-profiles/`

## 15.8 Billing and Background Checks

Billing:

- `/api/billing/health/`
- `/api/billing/exchange-rate/`
- `/api/billing/quotas/`
- `/api/billing/onboarding-token/`
- `/api/billing/onboarding-token/generate/`
- `/api/billing/onboarding-token/revoke/`
- `/api/billing/onboarding-token/send-invite/`
- `/api/billing/onboarding-token/validate/`
- `/api/billing/subscriptions/manage/`
- `/api/billing/subscriptions/manage/payment-method/update-session/`
- `/api/billing/subscriptions/manage/retry/`
- `/api/billing/subscriptions/confirm/`
- `/api/billing/subscriptions/access/verify/`
- `/api/billing/subscriptions/stripe/checkout-session/`
- `/api/billing/subscriptions/stripe/confirm/`
- `/api/billing/subscriptions/stripe/webhook/`
- `/api/billing/subscriptions/paystack/checkout-session/`
- `/api/billing/subscriptions/paystack/confirm/`
- `/api/billing/subscriptions/paystack/webhook/`

Background checks:

- `/api/background-checks/checks/`
- `/api/background-checks/checks/{id}/`
- `/api/background-checks/checks/{id}/events/`
- `/api/background-checks/checks/{id}/refresh/`
- `/api/background-checks/providers/{provider_key}/webhook/`

## 15.9 Government Appointments (GAMS)

Positions:

- `/api/positions/`
- `/api/positions/{id}/`
- `/api/positions/public/`
- `/api/positions/vacant/`
- `/api/positions/{id}/appointment-history/`

Personnel:

- `/api/personnel/`
- `/api/personnel/{id}/`
- `/api/personnel/officeholders/`
- `/api/personnel/{id}/link-candidate/`
- `/api/personnel/{id}/appointment-history/`

Approval chain:

- `/api/appointments/stage-templates/`
- `/api/appointments/stage-templates/{id}/`
- `/api/appointments/stages/`
- `/api/appointments/stages/{id}/`

Appointment lifecycle:

- `/api/appointments/records/`
- `/api/appointments/records/{id}/`
- `/api/appointments/records/{id}/ensure-vetting-linkage/`
- `/api/appointments/records/{id}/advance-stage/`
- `/api/appointments/records/{id}/appoint/`
- `/api/appointments/records/{id}/reject/`
- `/api/appointments/records/{id}/stage-actions/`
- `/api/appointments/records/{id}/publication/`
- `/api/appointments/records/{id}/publish/`
- `/api/appointments/records/{id}/revoke-publication/`

Public feeds:

- `/api/public/transparency/summary/`
- `/api/public/transparency/appointments/`
- `/api/public/transparency/appointments/gazette-feed/`
- `/api/public/transparency/appointments/open/`
- `/api/public/transparency/appointments/{id}/`
- `/api/public/transparency/positions/`
- `/api/public/transparency/positions/vacant/`
- `/api/public/transparency/officeholders/`
- `/api/appointments/records/gazette-feed/` (legacy compatibility, deprecated)
- `/api/appointments/records/open/` (legacy compatibility, deprecated)

## 15.10 Governance and Organization Management

Platform oversight:

- `/api/governance/platform/organizations/`
- `/api/governance/platform/organizations/{organization_id}/`

Organization setup and lookups:

- `/api/governance/organization/bootstrap/`
- `/api/governance/organization/summary/`
- `/api/governance/organization/lookups/member-options/`
- `/api/governance/organization/lookups/choices/`

Organization members and committees:

- `/api/governance/organization/members/`
- `/api/governance/organization/members/{id}/`
- `/api/governance/organization/committees/`
- `/api/governance/organization/committees/{id}/`
- `/api/governance/organization/committee-memberships/`
- `/api/governance/organization/committee-memberships/{id}/`

## 15.11 Government Alias Endpoints

These alias endpoints support government-domain naming while mapping to core resources:

- `/api/government/exercises/`
- `/api/government/exercises/{id}/`
- `/api/government/vetting-dossiers/`
- `/api/government/vetting-dossiers/{id}/`
- `/api/government/nominations/`
- `/api/government/nominations/{id}/`
- `/api/government/offices/`
- `/api/government/offices/{id}/`
