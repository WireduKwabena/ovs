# backend/apps/rubrics/templates.py
# From: Dynamic Vetting Rubrics PDF - Template section

from .models import VettingRubric, RubricCriteria

RUBRIC_TEMPLATES = {
    'standard_employment': {
        'name': 'Standard Employment Verification',
        'description': 'Basic employment verification for entry to mid-level positions',
        'rubric_type': 'employment',
        'passing_score': 70,
        'auto_approve_threshold': 85,
        'auto_reject_threshold': 50,
        'criteria': [
            {
                'name': 'Document Authenticity',
                'description': 'Verify documents are genuine and unaltered',
                'criteria_type': 'document_authenticity',
                'weight': 30,
                'minimum_score': 70,
                'is_mandatory': True,
                'scoring_rules': {
                    'aggregation': 'average',
                    'threshold_excellent': 95,
                    'threshold_good': 85,
                    'threshold_acceptable': 70
                }
            },
            {
                'name': 'OCR Quality',
                'description': 'Text extraction confidence',
                'criteria_type': 'ocr_confidence',
                'weight': 15,
                'minimum_score': 75,
                'is_mandatory': False,
                'scoring_rules': {
                    'min_acceptable': 80,
                    'target_score': 95
                }
            },
            {
                'name': 'Data Consistency',
                'description': 'Information consistency across documents',
                'criteria_type': 'data_consistency',
                'weight': 25,
                'minimum_score': 75,
                'is_mandatory': True,
                'scoring_rules': {
                    'min_acceptable': 75,
                    'target_score': 90
                }
            },
            {
                'name': 'Experience Requirements',
                'description': 'Minimum years of experience',
                'criteria_type': 'experience_years',
                'weight': 15,
                'minimum_score': 60,
                'is_mandatory': False,
                'scoring_rules': {
                    'required_years': 2,
                    'preferred_years': 5
                }
            },
            {
                'name': 'Fraud Risk Assessment',
                'description': 'Fraud detection score',
                'criteria_type': 'fraud_score',
                'weight': 15,
                'minimum_score': 70,
                'is_mandatory': False,
                'scoring_rules': {
                    'low_risk_threshold': 80,
                    'acceptable_risk': 60
                }
            }
        ]
    },
    
    'senior_position': {
        'name': 'Senior Position Vetting',
        'description': 'Comprehensive vetting for senior and executive positions',
        'rubric_type': 'employment',
        'passing_score': 80,
        'auto_approve_threshold': 92,
        'auto_reject_threshold': 60,
        'criteria': [
            {
                'name': 'Document Authenticity',
                'description': 'Strict authenticity verification',
                'criteria_type': 'document_authenticity',
                'weight': 25,
                'minimum_score': 85,
                'is_mandatory': True,
                'scoring_rules': {
                    'aggregation': 'minimum',
                    'threshold_excellent': 98,
                    'threshold_good': 90,
                    'threshold_acceptable': 85
                }
            },
            {
                'name': 'Senior Experience',
                'description': 'Extensive experience required',
                'criteria_type': 'experience_years',
                'weight': 30,
                'minimum_score': 80,
                'is_mandatory': True,
                'scoring_rules': {
                    'required_years': 7,
                    'preferred_years': 10
                }
            },
            {
                'name': 'Education Level',
                'description': 'Advanced degree preferred',
                'criteria_type': 'education_level',
                'weight': 20,
                'minimum_score': 75,
                'is_mandatory': False,
                'scoring_rules': {
                    'required_level': 'bachelor'
                }
            },
            {
                'name': 'Credential Validity',
                'description': 'All credentials must be verified',
                'criteria_type': 'credential_validity',
                'weight': 15,
                'minimum_score': 90,
                'is_mandatory': True,
                'scoring_rules': {
                    'default_score_no_credentials': 0
                }
            },
            {
                'name': 'Consistency Check',
                'description': 'High consistency required',
                'criteria_type': 'data_consistency',
                'weight': 10,
                'minimum_score': 80,
                'is_mandatory': True,
                'scoring_rules': {
                    'min_acceptable': 80,
                    'target_score': 95
                }
            }
        ]
    },
    
    'education_verification': {
        'name': 'Educational Credential Verification',
        'description': 'Verify educational qualifications and certificates',
        'rubric_type': 'education',
        'passing_score': 75,
        'auto_approve_threshold': 88,
        'auto_reject_threshold': 55,
        'criteria': [
            {
                'name': 'Certificate Authenticity',
                'description': 'Verify certificate is genuine',
                'criteria_type': 'document_authenticity',
                'weight': 40,
                'minimum_score': 80,
                'is_mandatory': True,
                'scoring_rules': {
                    'aggregation': 'average',
                    'threshold_excellent': 95,
                    'threshold_good': 85,
                    'threshold_acceptable': 75
                }
            },
            {
                'name': 'Credential Validity',
                'description': 'Credential verification',
                'criteria_type': 'credential_validity',
                'weight': 35,
                'minimum_score': 70,
                'is_mandatory': True,
                'scoring_rules': {
                    'default_score_no_credentials': 0
                }
            },
            {
                'name': 'Information Consistency',
                'description': 'Names and dates match',
                'criteria_type': 'data_consistency',
                'weight': 25,
                'minimum_score': 75,
                'is_mandatory': False,
                'scoring_rules': {
                    'min_acceptable': 75,
                    'target_score': 90
                }
            }
        ]
    },
    
    'background_check': {
        'name': 'Background Check Standard',
        'description': 'Standard background verification',
        'rubric_type': 'background',
        'passing_score': 75,
        'auto_approve_threshold': 90,
        'auto_reject_threshold': 55,
        'criteria': [
            {
                'name': 'Document Authenticity',
                'description': 'All documents must be authentic',
                'criteria_type': 'document_authenticity',
                'weight': 35,
                'minimum_score': 75,
                'is_mandatory': True,
                'scoring_rules': {
                    'aggregation': 'minimum',
                    'threshold_excellent': 95,
                    'threshold_good': 85,
                    'threshold_acceptable': 70
                }
            },
            {
                'name': 'Fraud Risk',
                'description': 'Low fraud risk required',
                'criteria_type': 'fraud_score',
                'weight': 40,
                'minimum_score': 75,
                'is_mandatory': True,
                'scoring_rules': {
                    'low_risk_threshold': 85,
                    'acceptable_risk': 70
                }
            },
            {
                'name': 'Data Consistency',
                'description': 'Cross-document consistency',
                'criteria_type': 'data_consistency',
                'weight': 25,
                'minimum_score': 70,
                'is_mandatory': True,
                'scoring_rules': {
                    'min_acceptable': 70,
                    'target_score': 85
                }
            }
        ]
    }
}


def create_rubric_from_template(template_key: str, created_by, **overrides):
    """
    Create a rubric from a template with optional overrides
    From: Rubrics PDF
    """
    template = RUBRIC_TEMPLATES.get(template_key)
    if not template:
        raise ValueError(f"Template '{template_key}' not found")
    
    # Apply overrides
    rubric_data = {**template, **overrides}
    criteria_data = rubric_data.pop('criteria')
    
    # Generate rubric ID
    import uuid
    rubric_data['rubric_id'] = f"RUB-{uuid.uuid4().hex[:8].upper()}"
    
    # Create rubric
    rubric = VettingRubric.objects.create(
        created_by=created_by,
        **rubric_data
    )
    
    # Create criteria
    for i, criterion_data in enumerate(criteria_data):
        RubricCriteria.objects.create(
            rubric=rubric,
            order=i,
            **criterion_data
        )
    
    return rubric