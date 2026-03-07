# OVS + GAMS User Manual

Version: 1.0  
Project: OVS-Redo (AI Vetting + Government Appointment Management)  
Audience: Administrators, HR Managers, Candidate Participants, and Technical Operators

## How To Use This Manual

This manual is organized into detailed chapters so each reader can start from their role and go directly to relevant procedures.

Print/continuous edition:

- [Single-file print manual](USER_MANUAL_PRINT.md)

Manual export tooling:

- PowerShell export script: `docs/scripts/export_user_manual.ps1`
- Example command:
  - `powershell -ExecutionPolicy Bypass -File docs/scripts/export_user_manual.ps1 -Formats pdf,docx,html`

## Table of Contents

1. [Getting Started](user-manual/01_getting_started.md)
2. [Roles, Permissions, and Navigation](user-manual/02_roles_permissions_navigation.md)
3. [Subscription, Billing, and Payment Methods](user-manual/03_subscription_billing_payment.md)
4. [Authentication, Login, and Security](user-manual/04_authentication_login_security.md)
5. [HR Campaign and Rubric Workflows](user-manual/05_hr_campaigns_rubrics.md)
6. [Candidate Invitations and Access Journey](user-manual/06_candidate_invitations_access.md)
7. [Applications and Document Vetting](user-manual/07_applications_documents_vetting.md)
8. [AI Interviews and Live Video Calls](user-manual/08_interviews_and_video_calls.md)
9. [Admin Operations and Control Center](user-manual/09_admin_operations_control_center.md)
10. [Monitoring, Audit Logs, and AI Runtime Health](user-manual/10_monitoring_audit_ai_health.md)
11. [Background Checks and Provider Integration](user-manual/11_background_checks_provider_ops.md)
12. [Notifications and Decision Lifecycle](user-manual/12_notifications_decisions.md)
13. [Operational Procedures (Docker, Commands, and Checks)](user-manual/13_operational_procedures.md)
14. [Troubleshooting Guide](user-manual/14_troubleshooting_guide.md)
15. [API Endpoint Quick Map](user-manual/15_api_endpoint_quick_map.md)
16. [Glossary and Best Practices](user-manual/16_glossary_best_practices.md)
17. [Frequently Asked Questions](user-manual/17_faq.md)
18. [Role Checklists and SOPs](user-manual/18_role_checklists_and_sops.md)

## Product Summary

This platform operates two integrated domains:

- OVS domain:
  - Campaign creation and rubric-driven scoring.
  - Candidate enrollment and invitation-based access.
  - Document verification (OCR, authenticity, fraud checks).
  - Interview analysis and live meeting scheduling.
  - Subscription, quota enforcement, and payment lifecycle.
- GAMS domain:
  - Government positions and personnel registries.
  - Appointment nomination, staged approval, and decision lifecycle.
  - Gazette/publication lifecycle and public-safe appointment feeds.
  - Appointment-specific audit events and notification flows.

## Core Principles

- AI recommendations never replace final human accountability.
- Permissions determine what each account can view and modify.
- Operational visibility is built in (health, logs, metrics, and events).
- Billing and quotas are enforced server-side, not only in UI.
- Public endpoints never expose internal vetting-only details.

## Who Should Read What First

- System Admin: Chapters 1, 2, 3, 4, 9, 10, 11, 13, 14, 15.
- HR Manager: Chapters 1, 2, 3, 4, 5, 6, 7, 8, 12, 14.
- Candidate User: Chapters 4, 6, 7, 8, 12, 14.
- Technical Operator: Chapters 1, 3, 4, 10, 11, 13, 14, 15.
