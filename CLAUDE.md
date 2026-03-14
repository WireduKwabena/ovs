# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Backend (Django + DRF)

- **Setup virtual environment**:

  ```bash
  cd backend
  python -m venv venv
  source venv/bin/activate  # Windows: venv\Scripts\activate
  pip install -r requirements/development.txt -c requirements/constraints.lock.txt
  ```

- **Database migrations**:

  ```bash
  python manage.py migrate
  ```

- **Create superuser**:

  ```bash
  python manage.py createsuperuser
  ```

- **Run development server**:

  ```bash
  python manage.py runserver
  ```

- **Run tests** (full suite):

  ```bash
  python manage.py test --keepdb
  ```

- **Run a single backend test** (replace `<path>` with the test file or dotted path):

  ```bash
  python manage.py test <path>
  ```

- **Run lint / type checks** (if applicable):

  ```bash
  python -m flake8 .
  mypy .
  ```

- **Start auxiliary services**:
  - Redis server: `redis-server`
  - Celery worker: `celery -A config worker -l info -E`
  - Celery beat: `celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler`
  - Flower UI: `celery -A config flower --port=5555`

### Frontend (React + Vite + TypeScript)

- **Install dependencies**:

  ```bash
  cd frontend
  npm install
  ```

- **Start development server**:

  ```bash
  npm run dev
  ```

- **Run lint**:

  ```bash
  npm run lint
  ```

- **Run type‑checking**:

  ```bash
  npm run type-check
  ```

- **Run full test suite**:

  ```bash
  npm test
  ```

- **Run a single frontend test** (provide path to the test file):

  ```bash
  vitest src/pages/HomePage.test.tsx --run
  ```

- **Build for CI** (includes type‑check and lint):

  ```bash
  npm run build:ci
  ```

## High‑Level Architecture

### Backend

- **Framework**: Django 5.x with Django REST Framework (DRF).
- **Apps** are grouped under `backend/apps/` and follow a standard Django app layout (models, serializers, views, urls, tests).
- **Core domains**:
  - **Vetting** (`apps/*`): campaigns, cases, interviews, rubrics, fraud detection, audit, monitoring.
  - **Government (GAMS)** (`apps/positions`, `apps/personnel`, `apps/appointments`, `apps/notifications`, `apps/audit`).
- **API**: Versioned REST endpoints under `/api/`. Internal/admin endpoints are protected; public transparency endpoints expose a sanitized view.
- **AI/ML services** live in `backend/ai_ml_services/` and are invoked via management commands (`train_ai_models`, `check_ai_ml_services`).
- **Async processing** via Celery workers (Redis broker) for background tasks such as document processing, model inference, and email notifications.
- **WebSockets** (Daphne ASGI server) for real‑time interview sessions.
- **Database**: PostgreSQL 15 with UUID primary keys across all models.

### Frontend

- **Framework**: React 18 with TypeScript, built using Vite.
- **Routing**: React Router manages `/government/*` pages (positions, personnel, appointments) and OVS‑related routes.
- **State management**: Redux Toolkit + React Query for server state.
- **Service layer**: `frontend/src/services/*.service.ts` encapsulates API calls to the backend.
- **Components**: Shared UI components live under `frontend/src/components/common/`; page‑level components under `frontend/src/pages/`.
- **Testing**: Vitest + React Testing Library; specialized test groups (`test:filters`, `test:ux-guards`).

## Notable Configuration Files

- `backend/manage.py` – entry point for Django commands.
- `backend/config/settings/*.py` – settings for development, testing, and production.
- `frontend/vite.config.ts` – Vite configuration, including proxy to the backend API.
- `docker-compose.yml` / `docker-compose.prod.yml` – Docker orchestration for all services.
- `.github/workflows/release-gate.yml` – CI pipeline enforcing lint, type‑check, tests, build, and OpenAPI validation.

## Additional Guidance

- Follow the **Release Gate** steps locally before pushing: run frontend lint, type‑check, tests, build:ci, coverage, then backend tests and `python manage.py check --deploy`.
- Use the provided management commands in `backend/ai_ml_services/commands/` for AI/ML model training and dataset generation.
- When adding new API endpoints, update the OpenAPI spec (`backend/openapi.yaml`) and ensure CI validates it.
- For debugging real‑time interview flows, connect to the Daphne ASGI server via the WebSocket URLs documented in the README.
