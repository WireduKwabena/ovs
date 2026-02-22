from __future__ import annotations

from typing import Any


class ApplicantContextExtractor:
    """Extract interview context from a vetting case and its documents."""

    SKILL_KEYWORDS = (
        "python",
        "javascript",
        "java",
        "management",
        "leadership",
        "communication",
        "analysis",
        "project management",
        "sql",
        "excel",
        "research",
        "design",
        "marketing",
    )

    @classmethod
    def extract_from_case(cls, case) -> dict[str, Any]:
        return {
            "basic_info": cls._extract_basic_info(case),
            "education": cls._extract_education(case),
            "experience": cls._extract_experience(case),
            "skills": cls._extract_skills(case),
            "documents_submitted": cls._list_documents(case),
            "inconsistencies_from_docs": cls._find_doc_inconsistencies(case),
        }

    @classmethod
    def extract_from_application(cls, application) -> dict[str, Any]:
        # Backward-compatible alias for old callers.
        return cls.extract_from_case(application)

    @staticmethod
    def _extract_basic_info(case) -> dict[str, Any]:
        applicant = case.applicant
        return {
            "name": applicant.get_full_name(),
            "email": applicant.email,
            "phone": applicant.phone_number,
            "position_applied": case.position_applied,
            "department": case.department,
            "case_id": case.case_id,
        }

    @staticmethod
    def _verification_data(document) -> dict[str, Any]:
        verification = getattr(document, "verification_result", None)
        if not verification:
            return {}
        return {
            "ocr_text": verification.ocr_text,
            "authenticity_score": verification.authenticity_score,
            "fraud_risk_score": verification.fraud_risk_score,
            "detailed_results": verification.detailed_results or {},
        }

    @classmethod
    def _extract_education(cls, case) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for document in case.documents.filter(document_type__in=["degree", "transcript"]).order_by("uploaded_at"):
            rows.append(
                {
                    "document_type": document.document_type,
                    "extracted_data": document.extracted_data or {},
                    "verification": cls._verification_data(document),
                }
            )
        return rows

    @classmethod
    def _extract_experience(cls, case) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for document in case.documents.filter(
            document_type__in=["employment_letter", "reference_letter", "other"]
        ).order_by("uploaded_at"):
            verification = getattr(document, "verification_result", None)
            rows.append(
                {
                    "document_type": document.document_type,
                    "text_extract": (verification.ocr_text[:500] if verification and verification.ocr_text else ""),
                    "extracted_data": document.extracted_data or {},
                    "verification": cls._verification_data(document),
                }
            )
        return rows

    @classmethod
    def _extract_skills(cls, case) -> list[str]:
        text_parts: list[str] = []
        for document in case.documents.all():
            if document.extracted_text:
                text_parts.append(document.extracted_text)
            verification = getattr(document, "verification_result", None)
            if verification and verification.ocr_text:
                text_parts.append(verification.ocr_text)

        corpus = " ".join(text_parts).lower()
        return [keyword for keyword in cls.SKILL_KEYWORDS if keyword in corpus]

    @classmethod
    def _list_documents(cls, case) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for document in case.documents.all().order_by("uploaded_at"):
            verification = getattr(document, "verification_result", None)
            rows.append(
                {
                    "type": document.document_type,
                    "status": document.status,
                    "authenticity_score": (
                        verification.authenticity_score if verification else None
                    ),
                    "fraud_risk_score": (
                        verification.fraud_risk_score if verification else None
                    ),
                }
            )
        return rows

    @classmethod
    def _extract_name_candidates(cls, document) -> list[str]:
        values: list[str] = []
        data_sources = [document.extracted_data or {}]
        verification = getattr(document, "verification_result", None)
        if verification and isinstance(verification.detailed_results, dict):
            data_sources.append(verification.detailed_results)

        for source in data_sources:
            for key in ("name", "full_name", "candidate_name", "applicant_name", "recipient_name"):
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())

        seen = set()
        normalized: list[str] = []
        for value in values:
            key = value.lower()
            if key not in seen:
                seen.add(key)
                normalized.append(value)
        return normalized

    @classmethod
    def _find_doc_inconsistencies(cls, case) -> list[dict[str, Any]]:
        inconsistencies: list[dict[str, Any]] = []

        names = set()
        for document in case.documents.all():
            for candidate in cls._extract_name_candidates(document):
                names.add(candidate.lower())
        if len(names) > 1:
            inconsistencies.append(
                {
                    "type": "name_variation",
                    "details": f"Different names found across documents: {', '.join(sorted(names))}",
                }
            )

        return inconsistencies
