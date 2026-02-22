"""Rubric templates aligned to the current rubric schema."""

from __future__ import annotations

from copy import deepcopy

from .models import RubricCriteria, VettingRubric


RUBRIC_TEMPLATES = {
    "standard_employment": {
        "name": "Standard Employment Verification",
        "description": "Balanced rubric for general employment vetting.",
        "rubric_type": "general",
        "document_authenticity_weight": 30,
        "consistency_weight": 20,
        "fraud_detection_weight": 25,
        "interview_weight": 20,
        "manual_review_weight": 5,
        "passing_score": 70,
        "auto_approve_threshold": 90,
        "auto_reject_threshold": 40,
        "minimum_document_score": 60,
        "maximum_fraud_score": 50,
        "require_interview": True,
        "critical_flags_auto_fail": True,
        "max_unresolved_flags": 2,
        "is_active": True,
        "is_default": False,
        "criteria": [
            {
                "name": "Document Authenticity",
                "description": "Validate authenticity and integrity of submitted documents.",
                "criteria_type": "document",
                "scoring_method": "ai_score",
                "weight": 40,
                "minimum_score": 65,
                "is_mandatory": True,
            },
            {
                "name": "Cross-document Consistency",
                "description": "Check consistency of identity/profile fields across all documents.",
                "criteria_type": "consistency",
                "scoring_method": "ai_score",
                "weight": 30,
                "minimum_score": 60,
                "is_mandatory": True,
            },
            {
                "name": "Interview Readiness",
                "description": "Assess interview quality and response coherence.",
                "criteria_type": "interview",
                "scoring_method": "ai_score",
                "weight": 30,
                "minimum_score": 60,
                "is_mandatory": False,
            },
        ],
    },
    "technical_position": {
        "name": "Technical Position Vetting",
        "description": "Vetting rubric for engineering and technical roles.",
        "rubric_type": "technical",
        "document_authenticity_weight": 25,
        "consistency_weight": 20,
        "fraud_detection_weight": 20,
        "interview_weight": 30,
        "manual_review_weight": 5,
        "passing_score": 75,
        "auto_approve_threshold": 92,
        "auto_reject_threshold": 45,
        "minimum_document_score": 65,
        "maximum_fraud_score": 45,
        "require_interview": True,
        "critical_flags_auto_fail": True,
        "max_unresolved_flags": 2,
        "is_active": True,
        "is_default": False,
        "criteria": [
            {
                "name": "Identity and Credentials",
                "description": "Verify technical credentials and supporting records.",
                "criteria_type": "document",
                "scoring_method": "ai_score",
                "weight": 35,
                "minimum_score": 70,
                "is_mandatory": True,
            },
            {
                "name": "Record Consistency",
                "description": "Ensure chronology and profile records are internally consistent.",
                "criteria_type": "consistency",
                "scoring_method": "ai_score",
                "weight": 25,
                "minimum_score": 65,
                "is_mandatory": True,
            },
            {
                "name": "Technical Interview Performance",
                "description": "Score technical communication and problem-solving quality.",
                "criteria_type": "technical",
                "scoring_method": "manual_rating",
                "weight": 40,
                "minimum_score": 65,
                "is_mandatory": True,
            },
        ],
    },
    "executive_screening": {
        "name": "Executive Screening Rubric",
        "description": "Higher-threshold rubric for executive and sensitive leadership hires.",
        "rubric_type": "executive",
        "document_authenticity_weight": 30,
        "consistency_weight": 25,
        "fraud_detection_weight": 25,
        "interview_weight": 15,
        "manual_review_weight": 5,
        "passing_score": 80,
        "auto_approve_threshold": 95,
        "auto_reject_threshold": 50,
        "minimum_document_score": 75,
        "maximum_fraud_score": 40,
        "require_interview": True,
        "critical_flags_auto_fail": True,
        "max_unresolved_flags": 1,
        "is_active": True,
        "is_default": False,
        "criteria": [
            {
                "name": "Document and Identity Confidence",
                "description": "Strict confidence requirements for document authenticity.",
                "criteria_type": "document",
                "scoring_method": "ai_score",
                "weight": 40,
                "minimum_score": 75,
                "is_mandatory": True,
            },
            {
                "name": "Background Consistency",
                "description": "Strict consistency checks across credential and history records.",
                "criteria_type": "consistency",
                "scoring_method": "ai_score",
                "weight": 35,
                "minimum_score": 70,
                "is_mandatory": True,
            },
            {
                "name": "Leadership Risk Review",
                "description": "Manual assessment for role-specific risk indicators.",
                "criteria_type": "behavioral",
                "scoring_method": "manual_rating",
                "weight": 25,
                "minimum_score": 65,
                "is_mandatory": False,
            },
        ],
    },
}


def create_rubric_from_template(template_key: str, created_by, **overrides):
    """
    Create or update a rubric from a named template and return it.

    Allowed overrides include any ``VettingRubric`` fields plus an optional
    ``criteria`` list to replace default template criteria.
    """

    template = RUBRIC_TEMPLATES.get(template_key)
    if template is None:
        raise ValueError(f"Template '{template_key}' not found")

    payload = deepcopy(template)
    payload.update(overrides)
    criteria_payload = payload.pop("criteria", [])

    rubric, _ = VettingRubric.objects.update_or_create(
        name=payload["name"],
        defaults={"created_by": created_by, **payload},
    )

    # Replace criteria set with template-defined criteria to keep template idempotent.
    rubric.criteria.all().delete()
    for index, item in enumerate(criteria_payload, start=1):
        RubricCriteria.objects.create(
            rubric=rubric,
            name=item["name"],
            description=item.get("description", ""),
            criteria_type=item.get("criteria_type", "custom"),
            scoring_method=item.get("scoring_method", "ai_score"),
            weight=item.get("weight", 0),
            minimum_score=item.get("minimum_score"),
            is_mandatory=item.get("is_mandatory", False),
            evaluation_guidelines=item.get("evaluation_guidelines", ""),
            display_order=item.get("display_order", index),
        )

    return rubric
