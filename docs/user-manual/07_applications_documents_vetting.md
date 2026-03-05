# 7) Applications and Document Vetting

## 7.1 Application Pages

Frontend routes:

- `/applications`
- `/applications/new`
- `/applications/:caseId`
- `/applications/:caseId/upload`

## 7.2 Application APIs

- `GET/POST /api/applications/cases/`
- `GET/PATCH/DELETE /api/applications/cases/{id}/`
- `POST /api/applications/cases/{id}/upload-document/`
- `GET /api/applications/cases/{id}/verification-status/`
- `POST /api/applications/cases/{id}/recheck-social-profiles/`

Document APIs:

- `GET/POST /api/applications/documents/`
- `GET/PATCH/DELETE /api/applications/documents/{id}/`

## 7.3 Document Vetting Components

The platform supports:

- OCR extraction,
- Authenticity scoring,
- Fraud risk scoring,
- Consistency checking,
- Social-profile consistency signals (where enabled).

## 7.4 Typical Case Workflow

1. Case created for a candidate.
2. Candidate uploads document set.
3. Case enters queued/processing analysis state.
4. Results are persisted and exposed in case detail.
5. HR reviews evidence and decides or escalates.

## 7.5 Verification Status Interpretation

Case status endpoint returns progress and outcomes that can include:

- pending/in-progress analysis,
- completed scoring outputs,
- flagged anomalies requiring human review.

Always treat low-confidence or conflicting signals as manual-review candidates.

## 7.6 Recheck Operations

Recheck endpoints can be used to:

- rerun social profile checks after profile updates,
- refresh stale analysis outputs,
- recover from transient provider failures.

## 7.7 Upload Guidance

To reduce verification errors:

1. Upload clear, readable, complete documents.
2. Avoid cropped corners or obscured IDs.
3. Keep file formats and naming conventions consistent.
4. Ensure candidate metadata matches submitted document identity fields.

## 7.8 Decision Quality Best Practices

Before final decision:

- Review both summary score and criterion-level outputs.
- Cross-check authenticity, fraud, and consistency outputs.
- Consider background check and interview context where available.
- Record rationale for overrides/escalations.

