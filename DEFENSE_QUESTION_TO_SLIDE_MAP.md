# Defense Question-to-Slide Map

Use this map when panel members interrupt and ask to jump directly to evidence.

## Fast Jump Table
| Panel question | Jump slide | Primary evidence | Backup artifact |
|---|---|---|---|
| What problem are you solving? | Slide 1 | Problem statement framing | `DEFENSE_2_MINUTE_EXEC_SUMMARY.md` |
| What exactly did you build? | Slide 2 | Scope bullets | `README.md` API/feature sections |
| How is the system architected? | Slide 3 | Topology diagram | `DEFENSE_ARCHITECTURE_ONE_PAGER.md` |
| Show full user flow end-to-end | Slide 4 | Workflow sequence | `DEFENSE_7_MINUTE_SCRIPT.md` (slides 4-5) |
| How does the AI component work? | Slide 5 | AI/ML pipeline + threshold routing | `backend/ai_ml_services/README.md` |
| How do you handle model uncertainty? | Slide 5 | Manual review routing statement | `DEFENSE_INTERRUPTION_QA.md` |
| How is security enforced? | Slide 6 | Roles, 2FA, CSRF/CORS controls | `backend/config/settings/base.py` |
| How do you enforce subscriptions/limits? | Slide 7 | Backend quota enforcement claim | `backend/apps/billing/quotas.py` |
| What happens when payment/webhook fails? | Slide 7 | Retry/reconciliation path | `backend/apps/billing/views.py` |
| How do you prove quality? | Slide 8 | Tests + release gate | `LAUNCH_READINESS_SCORECARD_2026-03-05.md` |
| Is this production-ready now? | Slide 9 | P0/P1/P2 readiness split | `LAUNCH_READINESS_SCORECARD_2026-03-05.md` |
| What are your biggest risks? | Slide 9 | Launch blockers + mitigations | `DEFENSE_INTERRUPTION_QA.md` |
| Why should we approve this project? | Slide 10 | Conclusion and next actions | `DEFENSE_2_MINUTE_EXEC_SUMMARY.md` |

## Interruption Routing Rules
1. If question is architecture/integration:
   - Jump to Slide 3, then open `DEFENSE_ARCHITECTURE_ONE_PAGER.md`.
2. If question is workflow/business value:
   - Jump to Slide 4, show sequence and decision points.
3. If question is AI trustworthiness:
   - Jump to Slide 5 and stress confidence thresholds + human final decision.
4. If question is security/compliance:
   - Jump to Slide 6 and cite role + audit + retention controls.
5. If question is launch status:
   - Jump to Slide 9 and answer with "production-oriented MVP, P0 hardening pending."

## 10-Second Transition Lines
- "Great question, I’ll jump to the architecture slide and show the exact boundary."
- "I’ll answer that by showing the end-to-end sequence from enrollment to final decision."
- "Let me jump to the readiness slide so you can see current P0 blockers and mitigation."

## If Asked for Direct Proof (Code/Runtime)
Use these quick references:
- Billing quota logic: `backend/apps/billing/quotas.py`
- Billing webhook/confirm behavior: `backend/apps/billing/views.py`
- Security/runtime config: `backend/config/settings/base.py`
- Production hardening checklist: `LAUNCH_READINESS_SCORECARD_2026-03-05.md`

