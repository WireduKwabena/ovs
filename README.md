# OVS-Redo (OVS + GAMS)

> Automated vetting and government appointment governance in one platform.

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18.2-61dafb.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## System Overview

This repository preserves the original OVS vetting engine while extending it into GAMS
(Government Appointment Management System).

Implemented today:

- OVS subsystems: campaigns, cases/applications, document verification, interviews, rubrics, fraud checks, notifications, audit.
- GAMS subsystems: position registry, personnel registry, appointment lifecycle, approval-chain governance, publication/gazette lifecycle, public feeds.

Key design rule:

- Extend existing OVS modules; do not replace them.

---

## Architecture Overview

### Backend (Django + DRF)

- `apps/campaigns`: appointment exercises and campaign-level governance metadata.
- `apps/applications`: vetting cases and document workflow.
- `apps/interviews`: AI-assisted interview sessions and analysis.
- `apps/rubrics`: rubric definitions and scoring outputs.
- `apps/positions`: `GovernmentPosition` registry and public/vacant views.
- `apps/personnel`: `PersonnelRecord` registry and controlled officeholder views.
- `apps/appointments`: `AppointmentRecord`, approval stages/templates, stage actions, publication lifecycle.
- `apps/notifications`: in-app/email/sms delivery + appointment lifecycle notifications.
- `apps/audit`: immutable operational history + event catalog.

### Frontend (React + TypeScript)

- Government routes:
  - `/government/positions`
  - `/government/personnel`
  - `/government/appointments`
- Service contract:
  - `frontend/src/services/government.service.ts`
- Core government pages:
  - `frontend/src/pages/GovernmentPositionsPage.tsx`
  - `frontend/src/pages/GovernmentPersonnelPage.tsx`
  - `frontend/src/pages/AppointmentsRegistryPage.tsx`

---

## Implemented GAMS Workflow

### Appointment States

`AppointmentRecord.status` values:

- `nominated`
- `under_vetting`
- `committee_review`
- `confirmation_pending`
- `appointed`
- `rejected`
- `withdrawn`
- `serving`
- `exited`

Allowed transitions (service-enforced):

- `nominated -> under_vetting | withdrawn`
- `under_vetting -> committee_review | withdrawn`
- `committee_review -> confirmation_pending | appointed | rejected | withdrawn`
- `confirmation_pending -> appointed | rejected | withdrawn`
- `appointed -> serving`
- `serving -> exited`

### Approval Chain

Approval chain is template-driven:

- `ApprovalStageTemplate` defines chain per exercise type.
- `ApprovalStage` defines ordered stages with:
  - `order`
  - `required_role`
  - `is_required`
  - `maps_to_status`

Hardening behavior implemented:

- Stage context is mandatory when moving to a status that has required mapped stages.
- Stage must belong to the appointment's approval template.
- Stage must map to requested target status.
- Required prior stages must already be completed.
- Actor must satisfy stage role; final decision (`appointed`/`rejected`) requires appointing-authority/admin privileges.

### Publication/Gazette Lifecycle

`AppointmentPublication` is 1:1 with `AppointmentRecord`:

- States: `draft`, `published`, `revoked`
- Provenance fields:
  - `published_by`, `published_at`
  - `revoked_by`, `revoked_at`, `revocation_reason`
  - `publication_reference`, `publication_document_hash`, `publication_notes`

Publication actions:

- Publish sets publication state to `published` and marks appointment public.
- Revoke requires `revocation_reason`; optionally makes appointment private (`make_private`, default `true`).

### Officeholder Integrity

Serving/exited transitions update linked registries:

- `serving`: position holder + vacancy state updated; nominee set to active officeholder.
- `exited`: exit date enforced; position vacancy/holder updated; nominee officeholder flag recalculated.

DB guardrails include:

- one serving appointment per position,
- unique active appointment per position+nominee,
- serving/exited require appointment date,
- exited requires exit date.

---

## Public vs Internal Data Rules

Internal endpoints (HR/admin restricted):

- `/api/positions/`
- `/api/personnel/`
- `/api/appointments/records/`
- stage actions, publish/revoke, linkage actions.

Public endpoints (safe serializers only):

- `/api/positions/public/`
- `/api/positions/vacant/`
- `/api/personnel/officeholders/`
- `/api/appointments/records/gazette-feed/`
- `/api/appointments/records/open/`

Public appointment feeds are additionally filtered to:

- `is_public=True`
- publication status `published`
- no internal vetting fields in response serializer.

Authenticated non-HR/admin users calling appointment history endpoints only receive records with `is_public=True`.

---

## Key API Endpoints (Current)

Government registries and lifecycle:

- `GET/POST /api/positions/`
- `GET /api/positions/public/`
- `GET /api/positions/vacant/`
- `GET /api/positions/{id}/appointment-history/`
- `GET/POST /api/personnel/`
- `GET /api/personnel/officeholders/`
- `POST /api/personnel/{id}/link-candidate/`
- `GET /api/personnel/{id}/appointment-history/`
- `GET/POST /api/appointments/records/`
- `POST /api/appointments/records/{id}/ensure-vetting-linkage/`
- `POST /api/appointments/records/{id}/advance-stage/`
- `POST /api/appointments/records/{id}/appoint/`
- `POST /api/appointments/records/{id}/reject/`
- `GET /api/appointments/records/{id}/stage-actions/`
- `GET /api/appointments/records/{id}/publication/`
- `POST /api/appointments/records/{id}/publish/`
- `POST /api/appointments/records/{id}/revoke-publication/`
- `GET /api/appointments/records/gazette-feed/`
- `GET /api/appointments/records/open/`
- `GET/POST /api/appointments/stage-templates/`
- `GET/POST /api/appointments/stages/`

Reused OVS core:

- campaigns, cases, interviews, rubrics, invitations, notifications, audit, fraud, monitoring endpoints remain active.

---

## 📦 Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

### Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/ai-vetting-system.git
   cd ai-vetting-system
   ```

2. **Setup backend**

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements/development.txt -c requirements/constraints.lock.txt

   # Optional: refresh lock after dependency updates
   # python -m pip freeze | sort > requirements/constraints.lock.txt
   
   # Create .env file
   cp .env.example .env
   # Edit .env with your database credentials
   # For worker/beat/flower, ensure: CELERY_EAGER=false
   # For S3-backed document operations, configure USE_S3 and AWS_* vars
   
   # Run migrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

### UUID Primary Key Schema Validation (PostgreSQL)

All managed models under `backend/apps/**` are expected to use UUID primary keys.

Run DB schema validation:

```bash
cd backend
python manage.py check_uuid_schema
```

If your existing local DB was created before the UUID migration update, recreate it with backup.
Run this from repository root:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/reset_dev_db_uuid.ps1 -Force
```

Dry run first:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/reset_dev_db_uuid.ps1
```

### S3 Document Storage Configuration

`documents.services.DocumentService` now expects S3 mode to be explicitly enabled.

Add these values in `backend/.env` when you want document upload/download/listing via S3:

```env
USE_S3=true
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

If `USE_S3=false` or the bucket is missing, `DocumentService` intentionally fails fast.

3. **Start Redis** (in separate terminal)

   ```bash
   redis-server
   ```

4. **Start Celery worker** (in separate terminal)

   ```bash
   cd backend
   celery -A config worker -l info -E
   ```

5. **Start Celery Beat** (in separate terminal)

   ```bash
   cd backend
   celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
   ```

6. **Start Flower** (optional monitoring UI)

   ```bash
   cd backend
   celery -A config flower --port=5555
   ```

7. **Start Django development server**

   ```bash
   python manage.py runserver
   ```

### Realtime (WebSocket) Setup

For interview realtime communication, keep Redis enabled and run an ASGI server.

1. **Set env vars in `backend/.env`**

   ```env
   USE_REDIS=true
   REDIS_URL=redis://localhost:6379/0
   CHANNELS_REDIS_URL=redis://localhost:6379/0
   ```

2. **Start Redis** (if not already running)

   ```bash
   redis-server
   ```

3. **Run ASGI app with Daphne** (recommended)

   ```bash
   cd backend
   daphne -b 0.0.0.0 -p 8000 config.asgi:application
   ```

4. **Connect from frontend/client**

   - `ws://localhost:8000/ws/interview/{session_id}/`
   - `ws://localhost:8000/ws/interviews/{session_id}/`

`python manage.py runserver` can work for basic local tests, but Daphne is recommended for stable websocket behavior.

8. **Setup frontend** (in separate terminal)

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

9. **Access the application**
   - Frontend: <http://localhost:3000>
   - Backend API: <http://localhost:8000/api/>
   - Django Admin: <http://localhost:8000/admin/>
   - Flower: <http://localhost:5555>

---

## 🗄️ Database Schema

The system uses 26 models across 6 Django apps:

### Core Models

- **VettingCase**: Main application/case entity
- **Document**: Uploaded documents with metadata
- **VerificationResult**: AI analysis results
- **InterviewSession**: Video interview sessions
- **InterviewResponse**: Individual Q&A with analysis
- **VettingRubric**: Scoring configuration

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for complete schema documentation.

---

## 🔬 AI/ML Components

### 1. Document Authenticity Detection

```python
# CNN model for detecting forged/altered documents
Input: Document image (PDF/JPG)
Output: Authenticity score (0-100)
Architecture: ResNet-based CNN
Training data: ~10,000 authentic + synthetic forgeries
```

Raw authenticity datasets can also be used directly from
`backend/ai_ml_services/datasets/raw_dataset/` by building a normalized
`metadata.csv` first:

```bash
cd backend
python ai_ml_services/datasets/create_dataset.py \
  --output_dir ai_ml_services/datasets/processed/main \
  --authentic_sources ai_ml_services/datasets/raw_dataset/CASIA2/Au \
  --forged_sources ai_ml_services/datasets/raw_dataset/CASIA2/Tp \
  --auto_labeled_sources ai_ml_services/datasets/raw_dataset/Dataset ai_ml_services/datasets/raw_dataset/ImSpliceDataset \
  --num_forgeries 2000

python manage.py train_ai_models --metadata-file ai_ml_services/datasets/processed/main/metadata.csv
```

### 2. Fraud Detection

```python
# ML classifier for fraud risk assessment
Input: Extracted document features (metadata, patterns, anomalies)
Output: Fraud probability (0-100)
Algorithm: Random Forest / XGBoost
Features: 50+ engineered features
```

### 3. Signature Authenticity

```python
# Dedicated signature verification model (CEDAR/GPDS-ready)
Input: Cropped signature image
Output: Genuine vs forged probability (0-100)
Algorithm: Handcrafted signature features + RandomForest
```

### 4. Video Interview Analysis

```python
# Multi-modal analysis pipeline
1. Audio → Whisper → Transcript
2. Text → Transformers → Sentiment
3. Video → OpenCV → Face presence
4. All → LLM (GPT-4/Claude) → Quality score
```

---

## 🧪 Testing

### Run Tests

```bash
# Backend tests
cd backend
python manage.py test --keepdb

# Focused orchestration + domain integration suites
python manage.py test --keepdb apps.campaigns apps.candidates apps.invitations apps.applications apps.interviews apps.rubrics

# Monitoring/audit/fraud suites
python manage.py test --keepdb apps.audit apps.fraud apps.ml_monitoring

# With coverage
coverage run --source='.' manage.py test --keepdb
coverage report

# Frontend tests
cd frontend
npm test

# Focused UX + quota guard tests
npm run test:ux-guards

# Focused filter + URL state tests
npm run test:filters
```

### Test Coverage Goals

- Unit tests: >80%
- Integration tests: >60%
- ML model accuracy: >85%

### Release Gate (CI + Local)

The repository now includes a strict full-stack release gate workflow:

- Workflow file: `.github/workflows/release-gate.yml`
- Frontend checks:
  - `npm run lint`
  - `npm run type-check`
  - `npm run test`
  - `npm run test:filters`
  - `npm run build:ci`
  - `npm run coverage:endpoints -- --strict`
- Backend checks:
  - Full Django test suite
  - `python manage.py check --deploy --settings=config.settings.production`
  - OpenAPI validation + drift check:
    - `python manage.py spectacular --file /tmp/openapi.generated.yaml --validate --settings=config.settings.production`
    - `diff -u backend/openapi.yaml /tmp/openapi.generated.yaml`

Recommended local pre-push gate run:

```bash
# frontend
cd frontend
npm run lint
npm run type-check
npm run test
npm run test:filters
npm run build:ci
npm run coverage:endpoints -- --strict

# backend
cd ../backend
python manage.py test --keepdb
python manage.py check --deploy --settings=config.settings.production
python manage.py spectacular --file openapi.yaml --validate --settings=config.settings.production
```

### GitHub Actions Artifacts (Release Gate)

When `.github/workflows/release-gate.yml` runs, it uploads artifacts to the workflow run summary:

- `frontend-ci-artifacts-<run_id>`
  - `dist/` bundle output (when build succeeds)
- `backend-ci-artifacts-<run_id>`
  - `backend-tests.log`
  - `deploy-check.log`
  - `openapi-check.log`
  - service logs on failure (`backend-service.log`, `db-service.log`, `redis-service.log`)
  - `openapi.generated.yaml` (schema generated during CI)

How to access:

1. Open the repository **Actions** tab.
2. Open a **Release Gate** run.
3. Download artifacts from the **Artifacts** panel at the bottom of the run page.

---

## 📊 Performance Benchmarks

### Document Processing

- OCR: ~2-5 seconds per page
- Authenticity detection: ~1-3 seconds per document
- Full document vetting: ~10-30 seconds (depending on page count)

### Video Analysis

- Transcription: ~1x realtime (10-minute video = ~10 minutes processing)
- Sentiment analysis: ~1 second
- Full interview analysis: ~1.2x interview duration

---

## 🎓 Academic Deliverables

### 1. Research Questions

- How does multimodal analysis compare to single-modal for deception detection?
- What is the optimal weight distribution in rubric evaluation?
- How reliable is LLM-based interview evaluation vs. human raters?

### 2. Datasets

- Document Authenticity: Custom dataset (authentic + synthetic forgeries)
- Interview Responses: Collected from volunteers (with consent)
- Ground Truth: Human expert evaluations for validation

### 3. Evaluation Metrics

- **Classification**: Precision, Recall, F1-score, ROC-AUC
- **Regression**: RMSE, MAE, R²
- **Agreement**: Cohen's Kappa (human vs. AI)

---

## 📖 Documentation

- **[User Manual](docs/USER_MANUAL.md)**: Operator-facing workflows and API quick map.
- **[Frontend Notes](frontend/README.md)**: Frontend module layout and government pages.
- **[Backend OpenAPI Snapshot](backend/openapi.yaml)**: Generated API contract snapshot.

User manual export (PDF/DOCX/HTML) via Pandoc:

```powershell
powershell -ExecutionPolicy Bypass -File docs/scripts/export_user_manual.ps1 -Formats pdf,docx,html
```

---

## 🚀 Deployment

### Using Docker (Recommended)

```bash
# Build and start all services
docker-compose up -d

# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser
```

Docker Compose now runs `backend`, `celery_worker`, `celery_beat`, and `flower`.
Flower UI is available at `http://localhost:5555`.

### Production Compose (No Bind Mounts)

Use the dedicated production stack file:

```bash
# 1) Build/publish images first (example local tags)
docker build -t ovs-redo-backend:latest -f Dockerfile .
docker build -t ovs-redo-frontend:latest -f frontend/Dockerfile frontend --build-arg VITE_API_URL=/api

# 2) Prepare prod env
cp .env.prod.example .env
# Edit DATABASE_URL, SECRET_KEY, ALLOWED_HOSTS, and FLOWER_BASIC_AUTH

# 3) Start production stack
docker compose -f docker-compose.prod.yml up -d
```

`docker-compose.prod.yml` uses prebuilt images and named volumes only (no source bind mounts).

### Manual Deployment

See `docs/user-manual/13_operational_procedures.md` for operational command reference.

---

## 🛣️ Current Status

This repository currently ships both OVS and GAMS flows in the same runtime:

- OVS: campaigns/cases/documents/interviews/rubrics/fraud/monitoring remain active.
- GAMS: positions/personnel/appointments/approval-chain/publication lifecycle are implemented and integrated.
- Audit + notifications include appointment-specific event coverage.
- Public government endpoints expose only curated serializer fields; internal vetting fields remain restricted.

Still evolving:

- Legacy naming/content in some non-government UX text and manual chapters remains OVS-oriented.
- Additional end-to-end demo polish and documentation harmonization can continue incrementally.

---

## 🤝 Contributing

This is an academic project, but contributions are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

- **Your Name** - *Initial work* - [YourGitHub](https://github.com/yourusername)

**Supervisor:** Dr. [Supervisor Name]  
**Institution:** [University Name]  
**Program:** Computer Science / Software Engineering  
**Year:** 2024/2025

---

## 🙏 Acknowledgments

- OpenAI for Whisper speech recognition
- HuggingFace for Transformers library
- Django and DRF communities
- Research papers that informed this work (see thesis bibliography)

---

## 📞 Contact

For questions or feedback:

- Email: <your.email@university.edu>
- LinkedIn: [Your Profile](https://linkedin.com/in/yourprofile)
- Project Link: [https://github.com/yourusername/ai-vetting-system](https://github.com/yourusername/ai-vetting-system)

---

**⭐ If this project helped you, please give it a star!**
