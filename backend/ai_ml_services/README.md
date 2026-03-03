# AI/ML Services Module

A Django service module providing AI/ML capabilities for document verification, fraud detection, and consistency checking. This module is designed to be imported and used directly by other Django apps, not as a standalone API service.

## Overview

The AI/ML Services module provides:

- **Document Verification**: OCR extraction, authenticity detection, and forgery detection
- **Fraud Detection**: ML-based fraud detection for applications
- **Consistency Checking**: Cross-document consistency verification
- **Background Processing**: Celery tasks for async processing

## Installation

This module is part of the Django backend. Ensure it's added to `INSTALLED_APPS` in your Django settings:

```python
INSTALLED_APPS = [
    ...
    'ai_ml_services.apps.AiMlServicesConfig',
    ...
]
```

## Usage

### Direct Function Calls (Synchronous)

For synchronous processing, import the service functions directly:

```python
from ai_ml_services import verify_document, detect_fraud, check_consistency

# Verify a document
result = verify_document(
    file_path='/path/to/document.pdf',
    document_type='id_card',
    case_id='APP-123'
)

print(result['results']['overall_score'])
print(result['results']['recommendation'])

# Detect fraud
fraud_result = detect_fraud(application_data={...})

# Check consistency
consistency_result = check_consistency(documents=[...])
```

### Async Processing with Celery Tasks

For background processing, use the provided Celery tasks:

```python
from ai_ml_services.utils.tasks import verify_document_task, detect_fraud_task

# Verify document asynchronously
task_result = verify_document_task.delay(
    document_id=123,
    file_path='/path/to/document.pdf',
    document_type='id_card',
    case_id='APP-123'
)

# Get task status
task = task_result.get()
print(task['success'])
```

## Integrating with Your Apps

### Example: Applications App

```python
# apps/applications/models.py
from django.db import models
from ai_ml_services.utils.tasks import verify_document_task

class Document(models.Model):
    file = models.FileField(upload_to='documents/')
    case_id = models.CharField(max_length=50)
    document_type = models.CharField(max_length=50)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Trigger AI verification
        verify_document_task.delay(
            document_id=self.id,
            file_path=self.file.path,
            document_type=self.document_type,
            case_id=self.case_id
        )
```

### Example: Handling Verification Results

```python
# apps/applications/processors.py
from ai_ml_services.utils.tasks import verify_document_task

def process_verification_result(task_result):
    """Handle the result from AI verification task."""
    if task_result['success']:
        ai_result = task_result['result']
        recommendation = ai_result['results']['recommendation']
        score = ai_result['results']['overall_score']

        if recommendation == 'APPROVE':
            # Document is authentic
            status = 'approved'
        elif recommendation == 'MANUAL_REVIEW':
            # Document needs manual review
            status = 'pending_review'
        else:
            # Document is rejected
            status = 'rejected'

        return {
            'status': status,
            'score': score,
            'ai_details': ai_result
        }
    else:
        return {
            'status': 'error',
            'error': task_result.get('error')
        }
```

## Available Functions

### `verify_document(file_path, document_type, case_id=None)`

Verify a single document for authenticity.

**Parameters:**

- `file_path` (str): Path to the document file
- `document_type` (str): Type of document (id_card, passport, certificate, etc.)
- `case_id` (str, optional): Case ID for tracking

**Returns:**

```python
{
    'success': True,
    'case_id': 'APP-123',
    'document_type': 'id_card',
    'results': {
        'ocr': {...},
        'authenticity': {
            'overall_score': 85.5,
            'deep_learning': {...},
            'computer_vision': {...}
        },
        'overall_score': 82.3,
        'recommendation': 'MANUAL_REVIEW',  # 'APPROVE'/'REJECT' only when model signals are healthy
        'automated_decision_allowed': False,
        'decision_constraints': [
            {'code': 'authenticity_model_unavailable', 'reason': '...'}
        ]
    },
    'processing_time': 2.45
}
```

### `detect_fraud(application_data)`

Detect fraud in application data.

**Parameters:**

- `application_data` (dict): Application information

**Returns:**

```python
{
    'is_fraud': False,
    'fraud_probability': 15.0,
    'anomaly_score': 15.0,
    'risk_level': 'low',  # or 'medium', 'high', 'critical'
    'confidence': 70.0,
    'recommendation': 'MANUAL_REVIEW',
    'automated_decision_allowed': False,
    'decision_constraints': [{'code': 'fraud_model_unavailable', 'reason': '...'}]
}
```

### `check_consistency(documents)`

Check consistency across multiple documents.

**Parameters:**

- `documents` (list): List of document dicts with 'text' and 'document_type'

**Returns:**

```python
{
    'overall_consistent': True,
    'overall_score': 88.5,
    'name_consistency': {...},
    'date_consistency': {...},
    'recommendation': 'Approve',
    'weights_used': {'name': 0.6, 'date': 0.4},
    'thresholds_used': {'approve': 85.0, 'manual_review': 70.0}
}
```

## Available Celery Tasks

### `verify_document_task(document_id, file_path, document_type, case_id)`

Async task for document verification.

### `detect_fraud_task(case_id, application_data)`

Async task for fraud detection.

### `check_consistency_task(case_id, documents)`

Async task for consistency checking.

### `batch_verify_documents_task(case_id, documents, default_document_type=None)`

Async task for batch document verification.

### `health_check_task()`

Health check for AI/ML services.

## Monitor Health Endpoint

Runtime monitor status is available at:

- `GET /api/ai-monitor/health/`
- `POST /api/ai-monitor/classify-document/`

Access rules:

- authenticated staff/admin user, or
- `X-Service-Token` header matching `SERVICE_TOKEN`.

Optional query params:

- `model_name` (default: `default`)

`POST /api/ai-monitor/classify-document/` accepts multipart form fields:

- `file` (required; image or PDF)
- `document_type` (optional declared type)
- `top_k` (optional, 1..5; default 3)

## Error Handling

All functions raise `AIServiceException` for errors:

```python
from ai_ml_services import verify_document, AIServiceException

try:
    result = verify_document('/path/to/doc.pdf', 'id_card', 'APP-123')
except AIServiceException as e:
    logger.error(f"AI service error: {e}")
```

## Configuration

The services are configured through environment variables and Django settings:

```python
# Settings for AI/ML services
AI_ML_RATE_LIMIT_PER_MINUTE = 120
AI_ML_RATE_LIMIT_REDIS_URL = 'redis://localhost:6379/1'
AI_ML_RATE_LIMIT_PATH_PREFIXES = ('/api/',)
AI_ML_MONITOR_ENABLED = True
AI_ML_MONITOR_USE_REDIS = True
AI_ML_MONITOR_REDIS_URL = 'redis://localhost:6379/2'
AI_ML_MONITOR_WINDOW_SIZE = 1000
AI_ML_MONITOR_MIN_CONFIDENCE_THRESHOLD = 0.7
AI_ML_MONITOR_MAX_PROCESSING_TIME = 5.0
AI_ML_MONITOR_DRIFT_WINDOW_SIZE = 100
AI_ML_MONITOR_DRIFT_THRESHOLD = 0.1
AI_ML_APPROVAL_THRESHOLD = 85.0
AI_ML_MANUAL_REVIEW_THRESHOLD = 70.0
AI_ML_CONSISTENCY_WEIGHTS = {"name": 0.6, "date": 0.4}
AI_ML_CONSISTENCY_THRESHOLDS = {"approve": 85.0, "manual_review": 70.0}
AI_ML_AUTHENTICITY_MODEL_PATH = "models/authenticity_best.h5"
AI_ML_AUTHENTICITY_TORCH_MODEL_PATH = "models/authenticity_detector.pth"
AI_ML_FRAUD_MODEL_PATH = "models/fraud_classifier.pkl"
AI_ML_SIGNATURE_MODEL_PATH = "models/signature_authenticity.pkl"
AI_ML_RVL_CDIP_MODEL_PATH = "models/rvl_cdip_classifier.pkl"
AI_ML_MIDV500_MODEL_PATH = "models/midv500_classifier.pkl"
AI_ML_POPPLER_PATH = ""  # optional Poppler bin directory if not on PATH
AI_ML_PDF_CONVERSION_WARNING_LIMIT = 5
AI_ML_IDENTITY_MATCH_THRESHOLD = 0.72
AI_ML_IDENTITY_EMBEDDING_BACKEND = "auto"  # auto | facenet | deepface
AI_ML_IDENTITY_FACENET_WEIGHTS = "vggface2"
AI_ML_IDENTITY_VIDEO_SAMPLE_RATE = 8
AI_ML_DOC_TYPE_MISMATCH_ENABLED = True
AI_ML_DOC_TYPE_MISMATCH_CONFIDENCE = 0.65
```

## Identity Match (Document vs Interview)

Run identity matching with FaceNet embeddings (preferred) or DeepFace fallback:

```python
from ai_ml_services.video.identity_matcher import IdentityMatcher

matcher = IdentityMatcher()
result = matcher.match_document_to_interview(
    document_path="media/documents/candidate_id.jpg",
    interview_video_path="media/interview_videos/response_001.mp4",
)
```

`run_interview_pipeline(...)` now accepts `document_path` and returns
`identity_match` in the response payload.

## Document Type Classification

After training (`train_document_classifiers`), `verify_document(...)` includes:

- `results.document_classification.rvl_cdip` (16-class document taxonomy prediction)
- `results.document_classification.midv500` (50-class ID type prediction)

Each payload includes `predicted_label`, `confidence`, and `top_k` scores when
the model artifact is available.

`verify_document(...)` also includes `results.document_type_alignment`. When
classifier confidence exceeds `AI_ML_DOC_TYPE_MISMATCH_CONFIDENCE`, declared
type mismatches are added as `document_type_mismatch` decision constraints.

## Dependencies

Required ML/AI libraries:

- tensorflow (for deep learning models)
- opencv-python (for image processing)
- facenet-pytorch (for identity embeddings)
- pytesseract, easyocr (for OCR)
- scikit-learn (for fraud detection)

## Testing

Run tests for the AI/ML services:

```bash
python manage.py test ai_ml_services.tests.test_service
```

## Reproducible Training

Use the built-in command to regenerate model artifacts used by runtime inference:

```bash
python manage.py train_ai_models \
  --auth-epochs 12 \
  --tf-epochs 10 \
  --fraud-samples 10000
```

Useful options:

- `--dry-run`: prints resolved paths/device and exits
- `--skip-authenticity` or `--skip-fraud`: train only a subset
- `--skip-signature`: skip signature model training
- `--metadata-file`: use an existing authenticity `metadata.csv` directly
- `--signature-metadata-file`: train signature model from dedicated signature metadata
- `--workspace`: temp training workspace (default `.tmp_ai_training`)
- `--keep-workspace`: retain generated training data for inspection
- `--max-auth-samples`: cap authenticity training samples for faster CPU runs
- `--freeze-backbone`: train only the classifier head for faster convergence on CPU
- `--forgery-types`: control forgery mix (`copy_move`, `resampling`, `jpeg`)
- `--copy-move-regions`: number of pasted regions per copy-move variant
- `--jpeg-quality-min`/`--jpeg-quality-max`: bound JPEG attack intensity
- `--verify-forgery-determinism`: assert reproducible forgery generation for the seed

After training, generate (or refresh) the model manifest used by strict preflight checks:

```bash
python manage.py generate_model_manifest --strict
```

Useful options:

- `--output`: custom manifest output path
- `--model-version`: fixed version string for every entry
- `--include-missing`: include missing configured artifacts as placeholder entries

## Using Raw Datasets

If your raw datasets are under `ai_ml_services/datasets/raw_dataset/`, build a normalized
authenticity dataset first:

```bash
python ai_ml_services/datasets/create_dataset.py \
  --output_dir ai_ml_services/datasets/processed/main \
  --authentic_sources ai_ml_services/datasets/raw_dataset/CASIA2/Au \
  --forged_sources ai_ml_services/datasets/raw_dataset/CASIA2/Tp \
  --auto_labeled_sources ai_ml_services/datasets/raw_dataset/Dataset ai_ml_services/datasets/raw_dataset/ImSpliceDataset \
  --coverage_sources ai_ml_services/datasets/raw_dataset/COVERAGE \
  --num_forgeries 2000 \
  --random_seed 42
```

`--coverage_sources` uses explicit COVERAGE parsing:

- `image/{id}.tif` -> authentic
- `image/{id}t.tif` -> forged

Then train directly from that metadata:

```bash
python manage.py train_ai_models \
  --metadata-file ai_ml_services/datasets/processed/main/metadata.csv \
  --auth-epochs 12 \
  --tf-epochs 10 \
  --fraud-samples 10000
```

For resume taxonomy data (for OCR/NLP and category modeling), create normalized resume metadata:

```bash
python ai_ml_services/datasets/create_resume_metadata.py \
  --source_dir ai_ml_services/datasets/raw_dataset/Resumes\ PDF \
  --output_dir ai_ml_services/datasets/processed/resumes \
  --val_ratio 0.15 \
  --test_ratio 0.15 \
  --min_samples_per_label 5
```

This writes:

- `metadata.csv` (filepath, normalized label, split)
- `labels.csv` (label to label_id mapping)
- `raw_to_normalized_labels.csv` (folder-name normalization map)

For RVL-CDIP document-type classification metadata:

```bash
python ai_ml_services/datasets/create_rvl_cdip_metadata.py \
  --source_dir ai_ml_services/datasets/raw_dataset/RVL-CDIP \
  --output_dir ai_ml_services/datasets/processed/rvl_cdip \
  --val_ratio 0.1 \
  --test_ratio 0.1 \
  --min_samples_per_label 10
```

For MIDV-500 identity-document metadata (preserves sequence IDs and frame-level quad annotations):

```bash
python ai_ml_services/datasets/create_midv500_metadata.py \
  --source_dir ai_ml_services/datasets/raw_dataset/midv500 \
  --output_dir ai_ml_services/datasets/processed/midv500 \
  --max_frames_per_sequence 30 \
  --val_ratio 0.1 \
  --test_ratio 0.1
```

MIDV output metadata includes:

- `source_type` (`template` or `frame`)
- `sequence_id` (camera/lighting sequence key like `CA`, `TS`)
- `annotation_path` and `quad_points` when frame JSON is available

Train document-type classifiers from those metadata files:

```bash
python manage.py train_document_classifiers \
  --rvl-metadata ai_ml_services/datasets/processed/rvl_cdip/metadata.csv \
  --midv-metadata ai_ml_services/datasets/processed/midv500/metadata.csv \
  --midv-source-types frame template
```

This writes model artifacts by default to:

- `models/rvl_cdip_classifier.pkl`
- `models/midv500_classifier.pkl`
- `models/document_classifier_training_report.json`

Use `--dry-run` to validate paths and metadata stats before training.

## Architecture

```
ai_ml_services/
├── __init__.py           # Public API exports
├── service.py            # Main orchestrator and service functions
├── utils/
│   ├── tasks.py         # Celery async tasks
│   └── schemas.py       # Shared DTO/dataclass schemas
├── apps.py             # Django app config
├── authenticity/        # Document authenticity detection
│   ├── authenticity_detector.py
│   ├── cv_detector.py
│   ├── consistency_checker.py
│   └── metadata_analyzer.py
├── fraud/              # Fraud detection
│   └── fraud_detector.py
├── ocr/                # OCR services
│   ├── ocr_service.py
│   └── structured_extractor.py
├── video/              # Video analysis and identity matching
├── interview/          # Interview engine
├── training/           # Model training utilities
├── datasets/           # Data utilities
├── utils/              # Helper utilities
└── tests/              # Unit tests
```

## Migration from FastAPI

If you were previously using the FastAPI version:

**Old (FastAPI):**

```python
response = requests.post(
    'http://ai-service:8000/api/verify-document',
    files={'file': open('doc.pdf', 'rb')},
    data={'document_type': 'id_card', 'case_id': 'APP-123'}
)
```

**New (Django Service):**

```python
from ai_ml_services import verify_document

result = verify_document(
    file_path='/path/to/doc.pdf',
    document_type='id_card',
    case_id='APP-123'
)
```

The results format is the same, but you now call the function directly instead of making HTTP requests.
