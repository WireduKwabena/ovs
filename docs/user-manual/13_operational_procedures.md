# 13) Operational Procedures (Docker, Commands, and Checks)

## 13.1 Standard Startup (Docker)

From project root:

```powershell
docker compose up -d --build
```

Validate service state:

```powershell
docker compose ps
```

Expected core services:

- `db`
- `redis`
- `backend`
- `celery_worker`
- `celery_beat`
- `flower`

## 13.2 Migrations and Admin Bootstrap

```powershell
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

## 13.3 Health and Integrity Checks

```powershell
docker compose exec backend python manage.py check --settings=config.settings.development
docker compose exec backend python manage.py check_uuid_schema
```

## 13.4 AI/ML Command Utilities

Command entrypoint examples:

```powershell
docker compose exec backend python manage.py check_ai_ml_services
docker compose exec backend python manage.py check_ai_ml_services --strict
docker compose exec backend python manage.py generate_model_manifest
docker compose exec backend python manage.py train_ai_models
docker compose exec backend python manage.py train_document_classifiers
```

## 13.5 Logging During Operations

Stream logs:

```powershell
docker compose logs -f backend
docker compose logs -f celery_worker
docker compose logs -f celery_beat
```

## 13.6 Release Gate Commands (Recommended)

Backend:

```powershell
docker compose exec backend python manage.py test --keepdb
docker compose exec backend python manage.py check --deploy --settings=config.settings.production
```

Frontend:

```powershell
npm --prefix frontend run lint
npm --prefix frontend run type-check
npm --prefix frontend run test
npm --prefix frontend run build:ci
npm --prefix frontend run coverage:endpoints -- --strict
```

## 13.7 Email Mode Validation

In development, confirm console email behavior:

```powershell
docker compose exec backend python manage.py shell -c "from django.conf import settings; print(settings.EMAIL_BACKEND)"
```

Expected in debug/development:

- `django.core.mail.backends.console.EmailBackend`

Expected in production settings:

- `django.core.mail.backends.smtp.EmailBackend`

## 13.8 Production Compose Notes

Use dedicated production compose file:

```powershell
docker compose -f docker-compose.prod.yml up -d
```

Production prerequisites:

- Hosted PostgreSQL `DATABASE_URL`,
- HTTPS origin settings,
- provider secrets (billing/background checks),
- rotated and secured credentials.

