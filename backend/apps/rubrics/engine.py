from __future__ import annotations

from django.utils import timezone

from apps.applications.models import VettingCase

from .models import RubricEvaluation, VettingRubric


class RubricEvaluationEngine:
    def __init__(self, case: VettingCase, rubric: VettingRubric):
        self.case = case
        self.rubric = rubric

    def evaluate(self, evaluated_by=None) -> RubricEvaluation:
        evaluation, _ = RubricEvaluation.objects.get_or_create(case=self.case, defaults={"rubric": self.rubric})
        evaluation.rubric = self.rubric
        evaluation.status = "in_progress"

        # Snapshot case scores into evaluation input fields.
        evaluation.document_authenticity_score = self.case.document_authenticity_score
        evaluation.consistency_score = self.case.consistency_score
        evaluation.fraud_risk_score = self.case.fraud_risk_score
        evaluation.interview_score = self.case.interview_score

        unresolved_flags = self.case.interrogation_flags.exclude(status__in=["resolved", "dismissed"])
        critical_exists = unresolved_flags.filter(severity="critical").exists()

        evaluation.unresolved_flags_count = unresolved_flags.count()
        evaluation.critical_flags_present = critical_exists
        evaluation.review_reasons = []

        baseline_avg = None
        available = [
            value
            for value in [
                evaluation.document_authenticity_score,
                evaluation.consistency_score,
                (100 - evaluation.fraud_risk_score) if evaluation.fraud_risk_score is not None else None,
                evaluation.interview_score,
            ]
            if value is not None
        ]
        if available:
            baseline_avg = sum(available) / len(available)

        criteria_scores = {}
        for criterion in self.rubric.criteria.all().order_by("display_order", "id"):
            if criterion.criteria_type == "document":
                score = evaluation.document_authenticity_score
            elif criterion.criteria_type == "consistency":
                score = evaluation.consistency_score
            elif criterion.criteria_type == "interview":
                score = evaluation.interview_score
            else:
                score = baseline_avg

            criteria_scores[str(criterion.id)] = {
                "name": criterion.name,
                "criteria_type": criterion.criteria_type,
                "score": score,
                "weight": criterion.weight,
                "minimum_score": criterion.minimum_score,
                "is_mandatory": criterion.is_mandatory,
                "passed": True if criterion.minimum_score is None else (score is not None and score >= criterion.minimum_score),
            }

        evaluation.criterion_scores = criteria_scores

        evaluation.status = "completed"
        evaluation.evaluated_at = timezone.now()
        evaluation.evaluated_by = evaluated_by
        evaluation.save()
        evaluation.refresh_from_db()

        recommendation = []
        if evaluation.final_decision == "auto_approved":
            recommendation.append("Auto-approved by rubric threshold.")
        elif evaluation.final_decision == "auto_rejected":
            recommendation.append("Auto-rejected by rubric threshold.")
        else:
            recommendation.append("Manual HR decision required.")
        if evaluation.requires_manual_review:
            recommendation.append("Manual review required due to rules/flags.")

        summary = (
            f"Rubric evaluation complete. Score={evaluation.total_weighted_score}, "
            f"decision={evaluation.final_decision}, unresolved_flags={evaluation.unresolved_flags_count}."
        )
        RubricEvaluation.objects.filter(pk=evaluation.pk).update(
            recommendations=" ".join(recommendation),
            evaluation_summary=summary,
        )
        evaluation.refresh_from_db()
        return evaluation

    
       
    def _evaluate_criterion(self, criterion: RubricCriteria) -> tuple:
        """
        Evaluate a single criterion
        From: Rubrics PDF - criterion evaluation
        """
        criterion_type = criterion.criteria_type
        scoring_rules = criterion.scoring_rules
        flags = []
        
        # Get AI verification results
        ai_results = self._get_ai_results()
        
        # Route to appropriate evaluator based on criterion type
        evaluators = {
            'document_authenticity': self._evaluate_authenticity,
            'ocr_confidence': self._evaluate_ocr_confidence,
            'data_consistency': self._evaluate_consistency,
            'fraud_score': self._evaluate_fraud_risk,
            'credential_validity': self._evaluate_credentials,
            'experience_years': self._evaluate_experience,
            'education_level': self._evaluate_education,
            'custom_field': self._evaluate_custom_field
        }
        
        evaluator = evaluators.get(criterion_type)
        
        if evaluator:
            score = evaluator(ai_results, scoring_rules, criterion)
        else:
            score = 0
            flags.append({
                'type': 'unknown_criterion',
                'message': f"Unknown criterion type: {criterion_type}"
            })
        
        return score, flags
    
    def _get_ai_results(self) -> Dict[str, Any]:
        """
        Aggregate all AI verification results for this application
        From: Rubrics PDF
        """
        documents = self.application.documents.all()
        
        results = {
            'document_authenticity_scores': [],
            'ocr_confidences': [],
            'consistency_score': self.application.consistency_score or 0,
            'fraud_risk_score': self.application.fraud_risk_score or 0,
            'documents': [],
            'extracted_data': []
        }
        
        for doc in documents:
            verification = doc.verification_results.first()
            if verification:
                results['document_authenticity_scores'].append(
                    verification.authenticity_score
                )
                results['ocr_confidences'].append(
                    verification.ocr_confidence
                )
                results['documents'].append({
                    'type': doc.document_type,
                    'authenticity': verification.authenticity_score,
                    'ocr_confidence': verification.ocr_confidence,
                    'verification_status': doc.verification_status,
                    'is_authentic': verification.is_authentic
                })
                results['extracted_data'].append(
                    verification.extracted_data
                )
        
        return results
    
    def _evaluate_authenticity(self, ai_results: Dict, rules: Dict, criterion: RubricCriteria) -> float:
        """
        Evaluate document authenticity based on AI scores and HR rules
        From: Rubrics PDF - authenticity evaluation
        """
        auth_scores = ai_results['document_authenticity_scores']
        
        if not auth_scores:
            return 0.0
        
        # Get scoring configuration from rules
        aggregation = rules.get('aggregation', 'average')
        threshold_excellent = rules.get('threshold_excellent', 95)
        threshold_good = rules.get('threshold_good', 85)
        threshold_acceptable = rules.get('threshold_acceptable', 70)
        
        # Calculate aggregate score based on aggregation method
        if aggregation == 'average':
            aggregate = sum(auth_scores) / len(auth_scores)
        elif aggregation == 'minimum':
            aggregate = min(auth_scores)
        elif aggregation == 'weighted':
            doc_weights = rules.get('document_weights', {})
            weighted_sum = 0
            total_weight = 0
            for i, score in enumerate(auth_scores):
                weight = doc_weights.get(str(i), 1)
                weighted_sum += score * weight
                total_weight += weight
            aggregate = weighted_sum / total_weight if total_weight > 0 else 0
        else:
            aggregate = sum(auth_scores) / len(auth_scores)
        
        # Convert to 0-100 score based on thresholds
        if aggregate >= threshold_excellent:
            return 100.0
        elif aggregate >= threshold_good:
            # Linear interpolation between good and excellent
            return 75 + ((aggregate - threshold_good) / (threshold_excellent - threshold_good)) * 25
        elif aggregate >= threshold_acceptable:
            # Linear interpolation between acceptable and good
            return 50 + ((aggregate - threshold_acceptable) / (threshold_good - threshold_acceptable)) * 25
        else:
            # Linear interpolation from 0 to acceptable
            return (aggregate / threshold_acceptable) * 50
    
    def _evaluate_ocr_confidence(self, ai_results: Dict, rules: Dict, criterion: RubricCriteria) -> float:
        """
        Evaluate OCR confidence scores
        From: Rubrics PDF
        """
        ocr_scores = ai_results['ocr_confidences']
        
        if not ocr_scores:
            return 0.0
        
        min_acceptable = rules.get('min_acceptable', 80)
        target_score = rules.get('target_score', 95)
        
        avg_confidence = sum(ocr_scores) / len(ocr_scores)
        
        if avg_confidence >= target_score:
            return 100.0
        elif avg_confidence >= min_acceptable:
            return 70 + ((avg_confidence - min_acceptable) / (target_score - min_acceptable)) * 30
        else:
            return (avg_confidence / min_acceptable) * 70
    
    def _evaluate_consistency(self, ai_results: Dict, rules: Dict, criterion: RubricCriteria) -> float:
        """
        Evaluate data consistency across documents
        From: Rubrics PDF
        """
        consistency_score = ai_results['consistency_score']
        
        if consistency_score is None:
            return 50.0  # Neutral score if not available
        
        min_acceptable = rules.get('min_acceptable', 75)
        target_score = rules.get('target_score', 90)
        
        if consistency_score >= target_score:
            return 100.0
        elif consistency_score >= min_acceptable:
            return 70 + ((consistency_score - min_acceptable) / (target_score - min_acceptable)) * 30
        else:
            return (consistency_score / min_acceptable) * 70
    
    def _evaluate_fraud_risk(self, ai_results: Dict, rules: Dict, criterion: RubricCriteria) -> float:
        """
        Evaluate fraud risk (inverse - lower risk = higher score)
        From: Rubrics PDF
        """
        fraud_risk = ai_results['fraud_risk_score']
        
        if fraud_risk is None:
            return 50.0
        
        # Invert score (low fraud risk = high score)
        # fraud_risk_score is 0-1, where 1 = high risk
        inverted_risk = 100 - (fraud_risk * 100)
        
        low_risk_threshold = rules.get('low_risk_threshold', 80)
        acceptable_risk = rules.get('acceptable_risk', 60)
        
        if inverted_risk >= low_risk_threshold:
            return 100.0
        elif inverted_risk >= acceptable_risk:
            return 70 + ((inverted_risk - acceptable_risk) / (low_risk_threshold - acceptable_risk)) * 30
        else:
            return (inverted_risk / acceptable_risk) * 70
    
    def _evaluate_credentials(self, ai_results: Dict, rules: Dict, criterion: RubricCriteria) -> float:
        """
        Evaluate credential validity
        From: Rubrics PDF
        """
        credential_docs = [
            d for d in ai_results['documents']
            if d['type'] in ['certificate', 'diploma', 'license']
        ]
        
        if not credential_docs:
            return rules.get('default_score_no_credentials', 50)
        
        # Count verified credentials
        verified_count = sum(
            1 for d in credential_docs
            if d['verification_status'] == 'verified' and d.get('is_authentic', False)
        )
        
        verification_rate = verified_count / len(credential_docs)
        
        return verification_rate * 100
    
    def _evaluate_experience(self, ai_results: Dict, rules: Dict, criterion: RubricCriteria) -> float:
        """
        Evaluate years of experience
        From: Rubrics PDF
        """
        required_years = rules.get('required_years', 0)
        preferred_years = rules.get('preferred_years', 5)
        
        # Extract experience from documents
        extracted_years = self._extract_experience_years(ai_results)
        
        if extracted_years >= preferred_years:
            return 100.0
        elif extracted_years >= required_years:
            return 70 + ((extracted_years - required_years) / (preferred_years - required_years)) * 30
        else:
            return (extracted_years / required_years) * 70 if required_years > 0 else 0
    
    def _evaluate_education(self, ai_results: Dict, rules: Dict, criterion: RubricCriteria) -> float:
        """
        Evaluate education level
        From: Rubrics PDF
        """
        required_level = rules.get('required_level', 'bachelor')
        
        education_levels = {
            'high_school': 1,
            'diploma': 2,
            'bachelor': 3,
            'master': 4,
            'phd': 5
        }
        
        detected_level = self._extract_education_level(ai_results)
        
        required_value = education_levels.get(required_level, 3)
        detected_value = education_levels.get(detected_level, 0)
        
        if detected_value >= required_value:
            return 100.0
        elif detected_value >= (required_value - 1):
            return 70.0
        else:
            return 40.0
    
    def _evaluate_custom_field(self, ai_results: Dict, rules: Dict, criterion: RubricCriteria) -> float:
        """
        Evaluate custom field defined by HR
        From: Rubrics PDF
        """
        field_name = rules.get('field_name')
        expected_value = rules.get('expected_value')
        comparison = rules.get('comparison', 'equals')
        
        actual_value = self._extract_custom_field(ai_results, field_name)
        
        if actual_value is None:
            return 0.0
        
        if comparison == 'equals':
            return 100.0 if str(actual_value).lower() == str(expected_value).lower() else 0.0
        elif comparison == 'contains':
            return 100.0 if str(expected_value).lower() in str(actual_value).lower() else 0.0
        elif comparison == 'greater_than':
            try:
                return 100.0 if float(actual_value) > float(expected_value) else 0.0
            except ValueError:
                return 0.0
        elif comparison == 'less_than':
            try:
                return 100.0 if float(actual_value) < float(expected_value) else 0.0
            except ValueError:
                return 0.0
        
        return 0.0
    
    def _get_recommendation(self, overall_score: float, flags: List) -> str:
        """
        Get AI recommendation based on score and flags
        From: Rubrics PDF
        """
        # Check for mandatory failures
        mandatory_failures = [f for f in flags if f['type'] == 'mandatory_failed']
        if mandatory_failures:
            return 'REJECT'
        
        # Check thresholds
        if self.rubric.auto_approve_threshold and overall_score >= self.rubric.auto_approve_threshold:
            return 'AUTO_APPROVE'
        elif self.rubric.auto_reject_threshold and overall_score < self.rubric.auto_reject_threshold:
            return 'AUTO_REJECT'
        elif overall_score >= self.rubric.passing_score:
            return 'APPROVE'
        else:
            return 'MANUAL_REVIEW'
    
    # Placeholder extraction methods
    def _extract_experience_years(self, ai_results: Dict) -> float:
        """
        Extract years of experience from employment documents
        Implementation would parse employment documents and calculate tenure
        """
        # Look for employment letters
        employment_docs = [
            data for data in ai_results['extracted_data']
            if data and ('start_date' in data or 'position' in data)
        ]
        
        if not employment_docs:
            return 0.0
        
        # Simple calculation: count employment documents * 2 years average
        # In production, parse actual dates and calculate
        return len(employment_docs) * 2.0
    
    def _extract_education_level(self, ai_results: Dict) -> str:
        """
        Extract education level from certificates
        Implementation would analyze certificate documents
        """
        # Look for education documents
        for data in ai_results['extracted_data']:
            if data and 'certificate_type' in data:
                cert_type = data['certificate_type'].lower()
                
                if 'phd' in cert_type or 'doctorate' in cert_type:
                    return 'phd'
                elif 'master' in cert_type:
                    return 'master'
                elif 'bachelor' in cert_type or 'degree' in cert_type:
                    return 'bachelor'
                elif 'diploma' in cert_type:
                    return 'diploma'
        
        return 'high_school'
    
    def _extract_custom_field(self, ai_results: Dict, field_name: str) -> Any:
        """
        Extract custom field from extracted data
        Implementation would search through all extracted data
        """
        for data in ai_results['extracted_data']:
            if data and field_name in data:
                return data[field_name]
        
        return None


    
