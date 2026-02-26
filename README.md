# AI-Powered Vetting System

## University Final Year Project

> **Automated background verification using Machine Learning and Computer Vision**

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18.2-61dafb.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Project Overview

An intelligent vetting system that automates background verification for HR processes using:

- **Document Analysis**: OCR, authenticity detection, and fraud detection
- **Video Interviews**: Automated transcription, sentiment analysis, and response evaluation
- **Dynamic Rubrics**: Configurable scoring system with human oversight

### Academic Focus

This project explores:

1. Multi-modal AI (combining document, audio, and video analysis)
2. Human-in-the-loop machine learning
3. Scalable microservices architecture
4. Real-world application of NLP and Computer Vision

### Integration Guide

See `INTEGRATION_MAP.md` for the repo-specific ownership model showing how
`campaigns` orchestrates `applications`, `rubrics`, and `interviews` without
replacing their responsibilities.

### Re-enabled Domain APIs

The legacy domain apps are now wired back into runtime:

- `GET/POST /api/applications/cases/`
- `POST /api/applications/cases/{id}/upload-document/`
- `GET /api/applications/cases/{id}/verification-status/`
- `GET /api/applications/documents/`
- `GET/POST /api/interviews/sessions/`
- `POST /api/interviews/sessions/{id}/start/`
- `POST /api/interviews/sessions/{id}/complete/`
- `GET/POST /api/interviews/questions/`
- `GET/POST /api/interviews/responses/`
- `POST /api/interviews/responses/{id}/analyze/`
- `GET/POST /api/interviews/feedback/`
- `GET/POST /api/rubrics/vetting-rubrics/`
- `POST /api/rubrics/vetting-rubrics/{id}/criteria/`
- `POST /api/rubrics/vetting-rubrics/{id}/evaluate-case/`
- `GET /api/rubrics/criteria/`
- `GET /api/rubrics/evaluations/`
- `POST /api/rubrics/evaluations/{id}/rerun/`
- `POST /api/rubrics/evaluations/{id}/override-criterion/`
- `GET /api/audit/logs/`
- `GET /api/audit/logs/recent-activity/`
- `GET /api/audit/logs/statistics/`
- `GET /api/fraud/results/`
- `GET /api/fraud/results/statistics/`
- `GET /api/fraud/consistency/`
- `GET /api/fraud/consistency/statistics/`
- `GET /api/ml-monitoring/`
- `GET /api/ml-monitoring/latest/`
- `GET /api/ml-monitoring/performance-summary/`
- `GET /api/ml-monitoring/history/?model_name=<name>`
- `GET /api/ml-monitoring/metrics/` (legacy alias)

---

## 🎯 Key Features

### Document Vetting

- ✅ OCR text extraction (Tesseract + EasyOCR)
- ✅ Document authenticity detection (CNN)
- ✅ Cross-document consistency checking
- ✅ Fraud risk assessment (ML classifier)
- ✅ Automatic flag generation for suspicious documents

### Video Interview Analysis

- ✅ Automated transcription (OpenAI Whisper)
- ✅ Sentiment analysis (HuggingFace Transformers)
- ✅ Face detection and presence tracking (OpenCV)
- ✅ LLM-based response evaluation (GPT-4/Claude)
- ✅ Dynamic question generation based on document flags

### Rubric System

- ✅ Configurable evaluation criteria
- ✅ Weighted scoring with customizable thresholds
- ✅ Automatic approve/reject with manual review option
- ✅ HR manager override capability
- ✅ Audit trail for all decisions

---

## 🚧 Phase 1 API (Implemented)

The backend now includes a phase-1 orchestration layer for campaign-driven vetting:

- `POST /api/campaigns/` - create campaign
- `POST /api/campaigns/{id}/rubrics/versions/` - create rubric version
- `GET /api/campaigns/{id}/dashboard/` - campaign progress summary
- `POST /api/campaigns/{id}/candidates/import/` - bulk candidate import (+ optional invitations)
- `GET/POST /api/candidates/` - candidate management
- `GET/POST /api/enrollments/` - candidate enrollment management
- `GET/POST /api/invitations/` - invitation creation/listing
- `POST /api/invitations/{id}/send/` - resend invitation
- `POST /api/invitations/accept/` - candidate invitation acceptance
- `POST /api/invitations/access/consume/` - candidate token/session bootstrap
- `GET /api/invitations/access/me/` - candidate session context
- `GET /api/invitations/access/results/` - candidate results endpoint
- `POST /api/invitations/access/logout/` - candidate session close
- `GET /api/audit/logs/` - audit history and statistics
- `GET /api/fraud/results/` - fraud model outputs per case
- `GET /api/fraud/consistency/` - consistency outputs per case
- `GET /api/ml-monitoring/` - current model metrics (admin/staff)

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────┐
│      React Frontend (TypeScript)        │
│  - Document upload                      │
│  - Video recorder                       │
│  - Results dashboard                    │
└────────────┬────────────────────────────┘
             │ REST API (HTTP)
┌────────────┴────────────────────────────┐
│       Django Backend + DRF              │
│  - PostgreSQL database                  │
│  - Celery async tasks                   │
│  - AI/ML processing                     │
└─────────────────────────────────────────┘
```

### Technology Stack

**Backend:**

- Django 4.2 (Web framework)
- Django REST Framework (API)
- PostgreSQL (Database)
- Celery + Redis (Async processing)
- PyTorch & TensorFlow (ML models)

**Frontend:**

- React 18 (UI framework)
- TypeScript (Type safety)
- Tailwind CSS (Styling)
- Axios (HTTP client)

**AI/ML:**

- OpenAI Whisper (Speech-to-text)
- HuggingFace Transformers (NLP)
- OpenCV (Computer vision)
- Tesseract & EasyOCR (OCR)
- Scikit-learn (ML algorithms)

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
python manage.py test

# Focused orchestration + domain integration suites
python manage.py test apps.campaigns apps.candidates apps.invitations apps.applications apps.interviews apps.rubrics

# Monitoring/audit/fraud suites
python manage.py test apps.audit apps.fraud apps.ml_monitoring

# With coverage
coverage run --source='.' manage.py test
coverage report

# Frontend tests
cd frontend
npm test
```

### Test Coverage Goals

- Unit tests: >80%
- Integration tests: >60%
- ML model accuracy: >85%

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

- **[Project Structure](PROJECT_STRUCTURE.md)**: Complete codebase documentation
- **[API Documentation](docs/API.md)**: REST API endpoints (auto-generated)
- **[User Manual](docs/USER_MANUAL.md)**: How to use the system
- **[Development Guide](docs/DEVELOPMENT.md)**: Contributing guidelines

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

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment guide.

---

## 🛣️ Roadmap

### Phase 1: MVP (Weeks 1-4) ✅

- [x] Database models
- [x] Django settings and configuration
- [ ] REST API endpoints
- [ ] Basic document upload

### Phase 2: Document Vetting (Weeks 5-8)

- [ ] OCR implementation
- [ ] Train authenticity CNN
- [ ] Train fraud classifier
- [ ] Consistency checker

### Phase 3: Video Interviews (Weeks 9-10)

- [ ] Whisper integration
- [ ] Sentiment analysis
- [ ] Face detection
- [ ] LLM evaluation

### Phase 4: Integration (Weeks 11-12)

- [ ] Frontend completion
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Documentation

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
