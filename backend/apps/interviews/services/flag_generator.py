"""Flag generation helpers from case document vetting artifacts."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from apps.applications.models import Document, InterrogationFlag, VettingCase


class InterrogationFlagGenerator:
    """Generate current-schema interrogation flags from a vetting case."""

    @classmethod
    def generate_flags_from_vetting(cls, case: VettingCase) -> List[Dict]:
        flags: List[Dict] = []
        flags.extend(cls._check_missing_core_documents(case))
        flags.extend(cls._check_authenticity_and_fraud(case))
        flags.extend(cls._check_consistency_signals(case))
        return flags

    @classmethod
    def sync_case_flags(
        cls,
        case: VettingCase,
        persist: bool = True,
        replace_pending: bool = False,
    ) -> Dict:
        payloads = cls.generate_flags_from_vetting(case)
        created_ids: List[int] = []

        if persist:
            if replace_pending:
                case.interrogation_flags.filter(status__in=["pending", "addressed"]).delete()

            for payload in payloads:
                flag = InterrogationFlag.objects.create(case=case, **payload)
                created_ids.append(flag.id)

        return {
            "case_id": case.case_id,
            "generated_count": len(payloads),
            "created_count": len(created_ids),
            "created_flag_ids": created_ids,
            "flags": payloads,
        }

    @staticmethod
    def _check_missing_core_documents(case: VettingCase) -> List[Dict]:
        submitted = set(case.documents.values_list("document_type", flat=True))
        payloads: List[Dict] = []

        identity_types = {"id_card", "passport", "drivers_license"}
        if submitted.isdisjoint(identity_types):
            payloads.append(
                {
                    "flag_type": "missing_information",
                    "severity": "high",
                    "title": "Missing identity document",
                    "description": "No valid identity document was submitted (id_card, passport, or drivers_license).",
                    "data_point": "identity_document",
                    "evidence": {"submitted_types": sorted(submitted)},
                    "suggested_questions": [
                        "Please explain why no government-issued identity document was submitted.",
                        "When can you provide an identity document for verification?",
                    ],
                }
            )

        if "employment_letter" not in submitted:
            payloads.append(
                {
                    "flag_type": "missing_information",
                    "severity": "medium",
                    "title": "Missing employment letter",
                    "description": "No employment letter was provided to validate current or recent employment.",
                    "data_point": "employment_letter",
                    "evidence": {"submitted_types": sorted(submitted)},
                    "suggested_questions": [
                        "Can you explain the absence of an employment letter?",
                        "Is there an alternative employment verification document you can provide?",
                    ],
                }
            )

        return payloads

    @staticmethod
    def _check_authenticity_and_fraud(case: VettingCase) -> List[Dict]:
        payloads: List[Dict] = []

        documents = case.documents.select_related("verification_result").all()
        for document in documents:
            verification = getattr(document, "verification_result", None)
            if verification is None:
                continue

            if verification.authenticity_score < 70:
                severity = "high" if verification.authenticity_score < 50 else "medium"
                payloads.append(
                    {
                        "flag_type": "authenticity_concern",
                        "severity": severity,
                        "title": f"Low authenticity score for {document.document_type}",
                        "description": (
                            f"{document.document_type} authenticity score is {verification.authenticity_score:.2f}, "
                            "which is below acceptance threshold."
                        ),
                        "data_point": document.document_type,
                        "evidence": {
                            "document_id": document.id,
                            "authenticity_score": verification.authenticity_score,
                            "authenticity_confidence": verification.authenticity_confidence,
                            "fraud_risk_score": verification.fraud_risk_score,
                        },
                        "suggested_questions": [
                            f"Can you explain how you obtained and prepared the {document.document_type}?",
                            "Do you have an alternative source copy from issuing authority?",
                        ],
                    }
                )

            if verification.fraud_risk_score > 50:
                severity = "critical" if verification.fraud_risk_score >= 80 else "high"
                payloads.append(
                    {
                        "flag_type": "fraud_indicator",
                        "severity": severity,
                        "title": f"High fraud risk for {document.document_type}",
                        "description": (
                            f"{document.document_type} fraud risk score is {verification.fraud_risk_score:.2f}, "
                            "requiring direct clarification."
                        ),
                        "data_point": document.document_type,
                        "evidence": {
                            "document_id": document.id,
                            "fraud_risk_score": verification.fraud_risk_score,
                            "fraud_prediction": verification.fraud_prediction,
                            "fraud_indicators": verification.fraud_indicators,
                        },
                        "suggested_questions": [
                            "Can you walk us through the source and custody chain of this document?",
                            "Who issued this document and when did you receive it?",
                        ],
                    }
                )

        return payloads

    @staticmethod
    def _extract_name_candidates(document: Document) -> List[str]:
        raw_values: List[str] = []

        data_sources = [document.extracted_data or {}]
        verification = getattr(document, "verification_result", None)
        if verification is not None:
            data_sources.append(verification.detailed_results or {})

        keys = ("name", "full_name", "candidate_name", "applicant_name")
        for source in data_sources:
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    raw_values.append(value.strip())

        normalized = []
        seen = set()
        for value in raw_values:
            key = value.lower().strip()
            if key and key not in seen:
                seen.add(key)
                normalized.append(value)
        return normalized

    @classmethod
    def _check_consistency_signals(cls, case: VettingCase) -> List[Dict]:
        documents = list(case.documents.all())
        values_to_docs: Dict[str, List[int]] = defaultdict(list)

        for document in documents:
            for value in cls._extract_name_candidates(document):
                values_to_docs[value.lower().strip()].append(document.id)

        if len(values_to_docs) <= 1:
            return []

        canonical_values = list(values_to_docs.keys())
        evidence = {
            "name_variants": canonical_values,
            "documents_by_variant": {key: value for key, value in values_to_docs.items()},
        }
        return [
            {
                "flag_type": "consistency_mismatch",
                "severity": "high",
                "title": "Name mismatch across submitted documents",
                "description": (
                    "Different name values were extracted across documents. "
                    "Candidate clarification is required."
                ),
                "data_point": "name",
                "evidence": evidence,
                "suggested_questions": [
                    "We observed name differences across your documents. Please explain each variation.",
                    "Which full legal name should be treated as canonical for this vetting process?",
                ],
            }
        ]
