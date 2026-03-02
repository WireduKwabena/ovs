# ai_service/services/consistency_checker.py
# From: AI/ML Implementation PDF - COMPLETE VERSION

import spacy
from difflib import SequenceMatcher
from datetime import datetime
from typing import Dict, List, Optional
import logging
from collections import Counter
import dateutil.parser
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_CONSISTENCY_WEIGHTS = {"name": 0.60, "date": 0.40}
DEFAULT_CONSISTENCY_THRESHOLDS = {"approve": 85.0, "manual_review": 70.0}


class ConsistencyChecker:
    """
    Cross-document consistency verification using NLP.

    This checker uses NLP to extract entities like names, dates, and addresses
    from multiple documents and then applies heuristic rules to check for
    consistency across them.
    """

    def __init__(self):
        """
        Initializes the ConsistencyChecker.
        """
        self.nlp, self.spacy_model_name = self._load_nlp_model()
        self.entity_extraction_available = "ner" in getattr(self.nlp, "pipe_names", [])
        self.weights = self._load_weights()
        self.thresholds = self._load_thresholds()
        logger.info(
            "Consistency Checker initialized (model=%s, ner_available=%s)",
            self.spacy_model_name,
            self.entity_extraction_available,
        )

    @staticmethod
    def _load_nlp_model():
        configured_model = str(
            getattr(
                settings,
                "AI_ML_CONSISTENCY_SPACY_MODEL",
                getattr(settings, "AI_ML_SPACY_MODEL", ""),
            )
            or ""
        ).strip()
        candidates = [configured_model] if configured_model else []
        for model_name in ("en_core_web_lg", "en_core_web_sm"):
            if model_name not in candidates:
                candidates.append(model_name)

        for model_name in candidates:
            try:
                return spacy.load(model_name), model_name
            except OSError:
                logger.warning(
                    "spaCy model '%s' is unavailable for consistency checks.",
                    model_name,
                )

        language = str(
            getattr(settings, "AI_ML_CONSISTENCY_SPACY_LANGUAGE", "en") or "en"
        ).strip()
        try:
            logger.warning(
                "Falling back to blank spaCy model '%s'; NER extraction will be limited.",
                language,
            )
            return spacy.blank(language), f"blank:{language}"
        except Exception:
            logger.warning(
                "Could not initialize blank spaCy model '%s'; using blank:en fallback.",
                language,
                exc_info=True,
            )
            return spacy.blank("en"), "blank:en"

    @staticmethod
    def _load_weights() -> Dict[str, float]:
        raw = getattr(settings, "AI_ML_CONSISTENCY_WEIGHTS", None)
        if not isinstance(raw, dict):
            return dict(DEFAULT_CONSISTENCY_WEIGHTS)

        try:
            name_weight = max(float(raw.get("name", DEFAULT_CONSISTENCY_WEIGHTS["name"])), 0.0)
            date_weight = max(float(raw.get("date", DEFAULT_CONSISTENCY_WEIGHTS["date"])), 0.0)
        except (TypeError, ValueError):
            return dict(DEFAULT_CONSISTENCY_WEIGHTS)

        total = name_weight + date_weight
        if total <= 0:
            return dict(DEFAULT_CONSISTENCY_WEIGHTS)
        return {"name": name_weight / total, "date": date_weight / total}

    @staticmethod
    def _load_thresholds() -> Dict[str, float]:
        raw = getattr(settings, "AI_ML_CONSISTENCY_THRESHOLDS", None)
        if not isinstance(raw, dict):
            return dict(DEFAULT_CONSISTENCY_THRESHOLDS)

        try:
            approve = float(raw.get("approve", DEFAULT_CONSISTENCY_THRESHOLDS["approve"]))
            manual_review = float(
                raw.get("manual_review", DEFAULT_CONSISTENCY_THRESHOLDS["manual_review"])
            )
        except (TypeError, ValueError):
            return dict(DEFAULT_CONSISTENCY_THRESHOLDS)

        approve = min(max(approve, 0.0), 100.0)
        manual_review = min(max(manual_review, 0.0), 100.0)
        if manual_review > approve:
            manual_review = approve
        return {"approve": approve, "manual_review": manual_review}

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities from text using spaCy."""
        doc = self.nlp(text or "")
        entities = {
            'persons': [ent.text for ent in doc.ents if ent.label_ == 'PERSON'],
            'organizations': [ent.text for ent in doc.ents if ent.label_ == 'ORG'],
            'dates': [ent.text for ent in doc.ents if ent.label_ == 'DATE'],
            'locations': [ent.text for ent in doc.ents if ent.label_ in ['GPE', 'LOC']],
            'money': [ent.text for ent in doc.ents if ent.label_ == 'MONEY'],
        }
        return entities

    def check_name_consistency(self, documents_data: List[Dict]) -> Dict:
        """Check if names are consistent across documents."""
        all_names = []
        name_sources = {}

        for doc in documents_data:
            text = doc.get('text', '')
            doc_type = doc.get('document_type', 'unknown')

            entities = self.extract_entities(text)
            for name in entities['persons']:
                all_names.append(name)
                name_sources.setdefault(name, []).append(doc_type)

            extracted = doc.get('extracted_data', {})
            for key in ['name', 'full_name', 'employee_name']:
                if name := extracted.get(key):
                    all_names.append(name)
                    name_sources.setdefault(name, []).append(doc_type)

        if len(all_names) < 2:
            return {'consistent': True, 'confidence': 100, 'reason': 'Insufficient data'}

        name_counts = Counter(all_names)
        most_common_name, _ = name_counts.most_common(1)[0]

        similarities = [
            SequenceMatcher(None, most_common_name.lower(), name.lower()).ratio()
            for name in all_names
        ]
        avg_similarity = sum(similarities) / len(similarities)
        
        consistent = avg_similarity > 0.8

        return {
            'consistent': consistent,
            'confidence': avg_similarity * 100,
            'most_common_name': most_common_name,
            'all_names': list(set(all_names)),
            'similarity_score': avg_similarity,
        }

    def check_date_consistency(self, documents_data: List[Dict]) -> Dict:
        """Check if dates are logically consistent using robust parsing."""
        dates_found = []

        for doc in documents_data:
            text = doc.get('text', '')
            doc_type = doc.get('document_type', 'unknown')

            # Extract from raw text
            entities = self.extract_entities(text)
            for date_str in entities['dates']:
                if parsed_date := self._parse_date(date_str):
                    dates_found.append({'date': parsed_date, 'source': doc_type, 'raw': date_str})
            
            # Extract from structured data
            extracted = doc.get('extracted_data', {})
            for key in ['date_of_birth', 'date_issued', 'start_date', 'end_date']:
                if date_str := extracted.get(key):
                    if parsed_date := self._parse_date(date_str):
                        dates_found.append({'date': parsed_date, 'source': f"{doc_type}:{key}", 'raw': date_str})

        if len(dates_found) < 2:
            return {'consistent': True, 'confidence': 100, 'reason': 'Insufficient dates'}

        # --- Logical Consistency Checks ---
        inconsistencies = []
        sorted_dates = sorted(dates_found, key=lambda x: x['date'])

        # Example check: Date of birth should be the earliest date
        dob = next((d for d in sorted_dates if 'birth' in d['source']), None)
        if dob and dob['date'] > sorted_dates[0]['date']:
            inconsistencies.append({
                'type': 'logical_error',
                'message': f"Date of birth '{dob['raw']}' is not the earliest date found.",
            })

        # Example check: No dates should be in the future
        now = timezone.now()
        for d in sorted_dates:
            if d['date'] > now:
                inconsistencies.append({
                    'type': 'future_date',
                    'message': f"Date in the future detected: {d['raw']}",
                })

        consistency_score = max(0, (1 - len(inconsistencies) / len(dates_found)) * 100)

        return {
            'consistent': len(inconsistencies) == 0,
            'confidence': consistency_score,
            'inconsistencies': inconsistencies,
            'date_timeline': [{'date': d['date'].isoformat(), 'source': d['source']} for d in sorted_dates]
        }

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string using the robust dateutil parser."""
        if not isinstance(date_str, str):
            return None
        try:
            # The fuzzy parameter can handle surrounding text
            parsed = dateutil.parser.parse(date_str.strip(), fuzzy=False)
            if timezone.is_naive(parsed):
                return timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed.astimezone(timezone.get_current_timezone())
        except (ValueError, OverflowError):
            return None

    def verify_all_documents(self, documents_data: List[Dict]) -> Dict:
        """
        Comprehensive consistency check across all documents.
        """
        name_check = self.check_name_consistency(documents_data)
        date_check = self.check_date_consistency(documents_data)
        # Other checks like address can be added here

        # --- Weighted Score Calculation ---
        overall_score = (
            name_check['confidence'] * self.weights['name'] +
            date_check['confidence'] * self.weights['date']
        )

        overall_consistent = name_check['consistent'] and date_check['consistent']

        # --- Recommendation ---
        if overall_score >= self.thresholds['approve']:
            recommendation = 'Approve'
        elif overall_score >= self.thresholds['manual_review']:
            recommendation = 'Manual Review'
        else:
            recommendation = 'Reject'

        return {
            'overall_consistent': overall_consistent,
            'overall_score': round(overall_score, 2),
            'name_consistency': name_check,
            'date_consistency': date_check,
            'recommendation': recommendation,
            'weights_used': self.weights,
            'thresholds_used': self.thresholds,
        }
