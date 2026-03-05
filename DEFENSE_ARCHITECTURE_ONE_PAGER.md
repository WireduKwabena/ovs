# Defense Architecture One-Pager

## 1) System Context (What the platform does)

- HR/Admin creates campaigns and rubrics.
- Candidates are enrolled and invited through secure links.
- Document + interview evidence is analyzed asynchronously.
- AI produces recommendations; final decision remains human-owned.
- Billing/subscription controls access and monthly quota.

## 2) Runtime Topology (Production-Oriented MVP)

```mermaid
flowchart LR
  subgraph FE["Frontend (React + TS)"]
    A1[Admin Portal]
    A2[HR Portal]
    A3[Candidate Access Flow]
  end

  subgraph API["Django API (DRF)"]
    B1[Auth + RBAC + 2FA]
    B2[Campaigns / Rubrics / Cases]
    B3[Billing + Quotas]
    B4[Video Calls + Scheduling]
    B5[Audit + Monitoring]
  end

  subgraph ASYNC["Async Runtime"]
    C1[Celery Worker]
    C2[Celery Beat]
    C3[Redis Broker/Cache]
  end

  subgraph DATA["Data + Artifacts"]
    D1[(PostgreSQL)]
    D2[(Media/Model Artifacts)]
  end

  subgraph EXT["External Providers"]
    E1[Stripe]
    E2[Paystack]
    E3[Background Check Provider]
    E4[LiveKit]
  end

  FE --> API
  API --> D1
  API --> D2
  API --> C3
  C1 --> C3
  C2 --> C3
  C1 --> D1
  C1 --> D2
  API <--> E1
  API <--> E2
  API <--> E3
  API <--> E4
```

## 3) Core Vetting Sequence (End-to-End)

```mermaid
sequenceDiagram
  participant HR as HR/Admin
  participant FE as Frontend
  participant API as Django API
  participant Q as Celery/Redis
  participant AI as ai_ml_services
  participant DB as PostgreSQL

  HR->>FE: Create campaign + rubric
  FE->>API: POST /api/campaigns + /rubrics
  API->>DB: Persist config

  HR->>FE: Import/enroll candidates
  FE->>API: POST import/enrollment
  API->>Q: enqueue invitations + checks

  Q->>AI: process document/interview tasks
  AI->>DB: save scores/evidence/flags

  FE->>API: Poll dashboard/status
  API->>DB: Read latest analysis + decision state
  API-->>FE: Case summary + recommendation

  HR->>FE: Approve/reject/escalate
  FE->>API: POST decision
  API->>Q: enqueue notifications/report jobs
```

## 4) Trust Boundaries and Controls

- Boundary A: Browser -> API
  - Controls: auth, role checks, CSRF/CORS constraints, 2FA flow (non-candidate accounts).
- Boundary B: API -> Async workers
  - Controls: task isolation, retry/backoff, queue-based decoupling.
- Boundary C: API -> External providers
  - Controls: signed webhook verification, idempotent state transitions, audit logs.
- Boundary D: Data storage
  - Controls: retention policy fields, immutable audit trail, quota-enforced API writes.

## 5) Failure Strategy (What happens when things go wrong)

- Provider timeout/failure: move to pending/open, retry or explicit confirm endpoint.
- Worker backlog: queue remains durable in Redis; health/runtime surfaces degraded state.
- AI low confidence: route to manual review path, not auto-fail.
- Billing webhook miss: confirm endpoint can reconcile provider state safely.

## 6) Why this architecture is defensible

- Keeps web API responsive by offloading expensive AI tasks.
- Preserves explainability with persisted evidence + model outputs.
- Supports incremental hardening without redesigning core modules.
- Aligns with launch controls in `LAUNCH_READINESS_SCORECARD_2026-03-05.md`.

## 7) 30-Second Close Statement

- "The system is architected as a production-oriented MVP: stable orchestration in Django, asynchronous AI execution with Celery/Redis, strict role-based flows, and provider-integrated billing/background checks. Remaining work is deployment hardening and operational runbooks, not core feasibility."
