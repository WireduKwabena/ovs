# Defense Pack Index

This is the single entry point for your project defense preparation.

## 1) Start Here (Order of Use)

1. `LAUNCH_READINESS_SCORECARD_2026-03-05.md`
2. `NIGHT_BEFORE_DEFENSE_CHECKLIST.md`
3. `DEFENSE_SLIDE_DECK_OUTLINE.md`
4. `DEFENSE_7_MINUTE_SCRIPT.md`
5. `DEFENSE_2_MINUTE_EXEC_SUMMARY.md`
6. `DEFENSE_INTERRUPTION_QA.md`
7. `DEFENSE_QUESTION_TO_SLIDE_MAP.md`
8. `DEFENSE_MOCK_PANEL_DRILL.md`
9. `DEFENSE_ARCHITECTURE_ONE_PAGER.md`

## 2) What Each File Is For

- `LAUNCH_READINESS_SCORECARD_2026-03-05.md`
  - Launch readiness status, P0/P1/P2 gaps, go/no-go logic.
- `NIGHT_BEFORE_DEFENSE_CHECKLIST.md`
  - 10-minute operational runbook with exact commands.
- `DEFENSE_SLIDE_DECK_OUTLINE.md`
  - Slide-by-slide structure with timing and content.
- `DEFENSE_7_MINUTE_SCRIPT.md`
  - Verbatim speaking script aligned to slide flow.
- `DEFENSE_2_MINUTE_EXEC_SUMMARY.md`
  - Fast opening summary for panel-first questions.
- `DEFENSE_INTERRUPTION_QA.md`
  - 15-second responses for common panel interruptions.
- `DEFENSE_QUESTION_TO_SLIDE_MAP.md`
  - Instant jump map from panel questions to slide + evidence.
- `DEFENSE_MOCK_PANEL_DRILL.md`
  - 20 realistic panel questions with strong answers and weak-answer traps.
- `DEFENSE_ARCHITECTURE_ONE_PAGER.md`
  - Diagram and system narrative for technical deep-dive questions.

## 3) 15-Minute Final Rehearsal Plan

1. Run service health and smoke checks from `NIGHT_BEFORE_DEFENSE_CHECKLIST.md`.
2. Do one full timed pass using `DEFENSE_7_MINUTE_SCRIPT.md`.
3. Review `DEFENSE_INTERRUPTION_QA.md` once.
4. Keep one fallback deterministic case ready.

## 4) Demo-Day Terminal Commands (Quick Copy)

```powershell
docker compose ps
docker compose exec backend python manage.py check --settings=config.settings.development
docker compose logs -f backend
docker compose logs -f celery_worker
```

## 5) If Live Demo Fails Midway

Use this line:

- "I’ll continue with a seeded deterministic case to demonstrate complete workflow behavior and auditability independent of provider uptime."

Then immediately switch to:

1. Completed case view
2. AI evidence summary
3. Decision history
4. Audit entries
