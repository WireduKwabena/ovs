# backend/apps/rubrics/engine.py
# From: Dynamic Vetting Rubrics PDF - Complete evaluation logic

from typing import Dict, List, Any
from .models import VettingRubric, RubricCriteria, RubricEvaluation
from apps.applications import VettingCase
import logging

logger = logging.getLogger(__name__)

class RubricEvaluationEngine:
    """
    Core engine for evaluating applications against HR-defined rubrics
    From: Rubrics PDF - Rubric Evaluation Engine section
    """
    
    def __init__(self, application: VettingCase, rubric: VettingRubric):
        self.application = application
        self.rubric = rubric
        self.criteria = rubric.criteria.all().order_by('order')
    
    def evaluate(self) -> RubricEvaluation:
        """
        Evaluate application against rubric
        From: Rubrics PDF - main evaluation logic
        """
        criteria_scores = {}
        total_weighted_score = 0
        total_weight = 0
        flags = []
        warnings = []
        
        # Evaluate each criterion
        for criterion in self.criteria:
            logger.info(f"Evaluating criterion: {criterion.name}")
            
            try:
                score, criterion_flags = self._evaluate_criterion(criterion)
            except Exception as e:
                logger.error(f"Error evaluating criterion {criterion.name}: {e}")
                score = 0
                criterion_flags = [{
                    'type': 'evaluation_error',
                    'criterion': criterion.name,
                    'error': str(e)
                }]
            
            # Store criterion score
            criteria_scores[criterion.id] = {
                'name': criterion.name,
                'score': score,
                'weight': criterion.weight,
                'weighted_score': score * (criterion.weight / 100),
                'minimum_required': criterion.minimum_score,
                'passed': score >= criterion.minimum_score,
                'is_mandatory': criterion.is_mandatory
            }
            
            total_weighted_score += score * (criterion.weight / 100)
            total_weight += criterion.weight
            
            # Check mandatory criteria
            if criterion.is_mandatory and score < criterion.minimum_score:
                flags.append({
                    'type': 'mandatory_failed',
                    'criterion': criterion.name,
                    'score': score,
                    'required': criterion.minimum_score,
                    'message': f"Mandatory criterion '{criterion.name}' not met (score: {score:.1f}%, required: {criterion.minimum_score}%)"
                })
            
            # Add criterion-specific flags
            flags.extend(criterion_flags)
        
        # Calculate overall score
        overall_score = (total_weighted_score / total_weight * 100) if total_weight > 0 else 0
        
        # Determine pass/fail
        passed = overall_score >= self.rubric.passing_score
        
        # Check for mandatory failures (overrides pass)
        mandatory_failures = [f for f in flags if f['type'] == 'mandatory_failed']
        if mandatory_failures:
            passed = False
        
        # Get AI recommendation
        ai_recommendation = self._get_recommendation(overall_score, flags)
        
        # Create evaluation record
        evaluation = RubricEvaluation.objects.create(
            application=self.application,
            rubric=self.rubric,
            overall_score=overall_score,
            criteria_scores=criteria_scores,
            passed=passed,
            ai_recommendation=ai_recommendation,
            evaluation_details={
                'total_weighted_score': total_weighted_score,
                'total_weight': total_weight,
                'passing_score': self.rubric.passing_score,
                'criteria_evaluated': len(self.criteria)
            },
            flags=flags,
            warnings=warnings
        )
        
        logger.info(f"Evaluation complete: {overall_score:.1f}% - {ai_recommendation}")
        
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