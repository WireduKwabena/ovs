"""
Fraud Detection Classifier
===========================

Machine learning model for document fraud detection.

Academic Note:
--------------
Supervised learning approach using engineered features:
1. Feature extraction from documents
2. Random Forest or XGBoost classifier
3. Anomaly detection for outliers
4. Ensemble voting for robustness

Research:
- Document fraud detection is a binary classification problem
- Features combine metadata, content, and behavioral signals
- Ensemble methods reduce false positives
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)
import joblib
from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class FraudDetector:
    """
    ML-based fraud detection for documents.
    
    Uses engineered features + ensemble classifier.
    
    Features:
    - Document metadata (file size, type, creation date)
    - Content features (text patterns, OCR confidence)
    - Authenticity scores (from CNN)
    - Consistency metrics (cross-document)
    """
    
    def __init__(
        self,
        model_type: str = 'random_forest',
        model_path: str = None
    ):
        """
        Initialize fraud detector.
        
        Args:
            model_type: 'random_forest' or 'gradient_boosting'
            model_path: Path to saved model (optional)
        """
        self.model_type = model_type
        self.model = None
        self.scaler = None
        self.feature_names = None
        
        if model_path:
            self.load_model(model_path)
        else:
            self._initialize_model()

        self._default_feature_order = [
            "num_documents",
            "avg_ocr_confidence",
            "avg_authenticity_score",
            "consistency_score",
            "submission_hour",
            "form_completeness",
            "word_count_normalized",
            "special_char_ratio",
            "has_metadata_ratio",
            "email_suspicious",
            "processing_time",
            "previous_applications",
        ]
    
    def _initialize_model(self):
        """Initialize ML model."""
        if self.model_type == 'random_forest':
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == 'gradient_boosting':
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        self.scaler = StandardScaler()
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str] = None
    ) -> Dict:
        """
        Train fraud detection model.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (0 = legitimate, 1 = fraudulent)
            feature_names: Optional feature names
        
        Returns:
            Training metrics
        """
        logger.info(f"Training fraud detector on {len(X)} samples")
        
        # Store feature names
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_prob = self.model.predict_proba(X_test_scaled)[:, 1]
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'f1': f1_score(y_test, y_pred),
            'auc': roc_auc_score(y_test, y_prob),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist()
        }
        
        # Cross-validation
        cv_scores = cross_val_score(
            self.model, X_train_scaled, y_train,
            cv=5, scoring='f1'
        )
        metrics['cv_f1_mean'] = cv_scores.mean()
        metrics['cv_f1_std'] = cv_scores.std()
        
        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
            metrics['feature_importance'] = dict(zip(
                self.feature_names,
                importance.tolist()
            ))
        
        logger.info(f"Training complete: F1={metrics['f1']:.3f}, AUC={metrics['auc']:.3f}")
        
        return metrics
    
    def predict(self, features: np.ndarray) -> Dict:
        """
        Predict fraud probability.
        
        Args:
            features: Feature vector (1D or 2D array)
        
        Returns:
            {
                'fraud_probability': float (0-100),
                'is_fraudulent': bool,
                'risk_level': str,
                'confidence': float
            }
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Ensure 2D
        if features.ndim == 1:
            features = features.reshape(1, -1)
        
        # Scale
        features_scaled = self.scaler.transform(features)
        
        # Predict
        prob = self.model.predict_proba(features_scaled)[0, 1]
        prediction = self.model.predict(features_scaled)[0]
        
        # Determine risk level
        if prob < 0.3:
            risk_level = 'low'
        elif prob < 0.6:
            risk_level = 'medium'
        elif prob < 0.8:
            risk_level = 'high'
        else:
            risk_level = 'critical'
        
        # Confidence (distance from decision boundary)
        confidence = abs(prob - 0.5) * 200  # 0-100
        
        return {
            'fraud_probability': round(prob * 100, 2),
            'is_fraudulent': bool(prediction),
            'risk_level': risk_level,
            'confidence': round(confidence, 2)
        }
    
    def explain_prediction(self, features: np.ndarray) -> Dict:
        """
        Explain fraud prediction using feature importance.
        
        Args:
            features: Feature vector
        
        Returns:
            {
                'prediction': dict,
                'top_indicators': list,
                'explanation': str
            }
        """
        prediction = self.predict(features)
        
        # Get feature contributions (simplified SHAP-like)
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
            features_flat = features.flatten()
            
            # Calculate feature contributions
            contributions = importance * features_flat
            
            # Get top indicators
            top_indices = np.argsort(contributions)[-5:][::-1]
            top_indicators = [
                {
                    'feature': self.feature_names[i],
                    'value': float(features_flat[i]),
                    'importance': float(importance[i]),
                    'contribution': float(contributions[i])
                }
                for i in top_indices
            ]
        else:
            top_indicators = []
        
        # Generate explanation
        if prediction['is_fraudulent']:
            explanation = f"Document classified as FRAUDULENT (probability: {prediction['fraud_probability']}%). "
            explanation += f"Risk level: {prediction['risk_level']}. "
            if top_indicators:
                top_feature = top_indicators[0]
                explanation += f"Primary indicator: {top_feature['feature']}."
        else:
            explanation = f"Document appears LEGITIMATE (fraud probability: {prediction['fraud_probability']}%)."
        
        return {
            'prediction': prediction,
            'top_indicators': top_indicators,
            'explanation': explanation
        }
    
    def save_model(self, model_path: str):
        """Save trained model to disk."""
        model_path = Path(model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save model, scaler, and feature names
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'model_type': self.model_type
        }, model_path)
        
        logger.info(f"Model saved to {model_path}")
    
    def load_model(self, model_path: str):
        """Load trained model from disk."""
        data = joblib.load(model_path)
        
        self.model = data['model']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.model_type = data.get('model_type', 'random_forest')
        
        logger.info(f"Model loaded from {model_path}")

    def _build_feature_dict(self, application_data: Dict) -> Dict[str, float]:
        """Create normalized fraud features from request payload."""
        documents = application_data.get("documents") or []
        num_docs = len(documents)

        def _avg(key: str, default: float = 0.0, scale: float = 1.0) -> float:
            if not documents:
                return default
            values = []
            for doc in documents:
                value = doc.get(key)
                if value is None:
                    continue
                try:
                    values.append(float(value) / scale)
                except (TypeError, ValueError):
                    continue
            if not values:
                return default
            return float(np.mean(values))

        submission_hour = (
            application_data.get("submission_time", {}) or {}
        ).get("hour", 12)
        try:
            submission_hour = float(submission_hour)
        except (TypeError, ValueError):
            submission_hour = 12.0

        consistency_score = (
            (application_data.get("consistency_check", {}) or {}).get("overall_score")
        )
        if consistency_score is None:
            consistency_score = 80.0
        try:
            consistency_score = float(consistency_score) / 100.0
        except (TypeError, ValueError):
            consistency_score = 0.8

        email_value = str(application_data.get("email", "")).strip().lower()
        suspicious_email = int(
            not email_value
            or any(token in email_value for token in ("test@", "temp", "fake", "noreply"))
        )

        processing_time = application_data.get("processing_time")
        if processing_time is None:
            processing_time = 180.0
        try:
            processing_time = float(processing_time)
        except (TypeError, ValueError):
            processing_time = 180.0

        previous_applications = application_data.get("previous_applications", 0)
        try:
            previous_applications = float(previous_applications)
        except (TypeError, ValueError):
            previous_applications = 0.0

        form_completeness = application_data.get("form_completeness", 0.85)
        try:
            form_completeness = float(form_completeness)
        except (TypeError, ValueError):
            form_completeness = 0.85
        form_completeness = min(max(form_completeness, 0.0), 1.0)

        text_payload = " ".join(str(doc.get("text", "")) for doc in documents).strip()
        total_chars = len(text_payload)
        total_words = len(text_payload.split())
        word_count_normalized = min(total_words / 500.0, 1.0)
        special_char_ratio = (
            sum(1 for char in text_payload if not char.isalnum() and not char.isspace()) / total_chars
            if total_chars > 0
            else 0.1
        )

        has_metadata_ratio = _avg("has_metadata", default=0.5, scale=1.0)
        avg_ocr_confidence = _avg("ocr_confidence", default=0.75, scale=100.0)
        avg_authenticity_score = _avg("authenticity_score", default=0.75, scale=100.0)

        return {
            "num_documents": float(num_docs),
            "avg_ocr_confidence": avg_ocr_confidence,
            "avg_authenticity_score": avg_authenticity_score,
            "consistency_score": consistency_score,
            "submission_hour": submission_hour,
            "form_completeness": form_completeness,
            "word_count_normalized": word_count_normalized,
            "special_char_ratio": float(special_char_ratio),
            "has_metadata_ratio": has_metadata_ratio,
            "email_suspicious": float(suspicious_email),
            "processing_time": processing_time,
            "previous_applications": previous_applications,
        }

    def _feature_vector_for_inference(self, feature_dict: Dict[str, float]) -> np.ndarray:
        order = self.feature_names or self._default_feature_order
        vector = [float(feature_dict.get(name, 0.0)) for name in order]
        return np.asarray(vector, dtype=np.float32)

    @staticmethod
    def _risk_level_from_probability(probability: float) -> str:
        if probability < 30:
            return "low"
        if probability < 60:
            return "medium"
        if probability < 80:
            return "high"
        return "critical"

    def _heuristic_predict(self, feature_dict: Dict[str, float]) -> Dict:
        """Fallback prediction when no fitted model is available."""
        risk = 0.0

        if feature_dict["num_documents"] < 2:
            risk += 20
        if feature_dict["avg_ocr_confidence"] < 0.60:
            risk += 25
        elif feature_dict["avg_ocr_confidence"] < 0.75:
            risk += 12

        if feature_dict["avg_authenticity_score"] < 0.60:
            risk += 30
        elif feature_dict["avg_authenticity_score"] < 0.75:
            risk += 15

        if feature_dict["consistency_score"] < 0.60:
            risk += 20
        elif feature_dict["consistency_score"] < 0.75:
            risk += 10

        if feature_dict["email_suspicious"] > 0:
            risk += 8

        if feature_dict["submission_hour"] < 6 or feature_dict["submission_hour"] > 23:
            risk += 7

        if feature_dict["special_char_ratio"] > 0.20:
            risk += 6

        if feature_dict["has_metadata_ratio"] < 0.40:
            risk += 8

        fraud_probability = float(min(max(risk, 0.0), 100.0))
        is_fraud = fraud_probability >= 60.0
        risk_level = self._risk_level_from_probability(fraud_probability)
        confidence = float(abs(fraud_probability - 50.0) * 2.0)

        return {
            "is_fraud": is_fraud,
            "is_fraudulent": is_fraud,
            "fraud_probability": round(fraud_probability, 2),
            "anomaly_score": round(fraud_probability, 2),
            "risk_level": risk_level,
            "confidence": round(confidence, 2),
            "recommendation": "MANUAL_REVIEW",
            "automated_decision_allowed": False,
            "decision_constraints": [
                {
                    "code": "fraud_model_unavailable",
                    "reason": "Heuristic fraud signal is advisory and requires human review.",
                }
            ],
            "mode": "heuristic",
        }

    def predict_fraud(self, application_data: Dict) -> Dict:
        """
        Predict fraud directly from application payload.
        Returns a stable contract for orchestrator/tasks.
        """
        feature_dict = self._build_feature_dict(application_data)
        features = self._feature_vector_for_inference(feature_dict)

        model_ready = (
            self.model is not None
            and self.scaler is not None
            and hasattr(self.scaler, "mean_")
            and hasattr(self.model, "predict_proba")
        )
        if not model_ready:
            return self._heuristic_predict(feature_dict)

        prediction = self.predict(features)
        fraud_probability = float(prediction["fraud_probability"])
        is_fraud = bool(prediction["is_fraudulent"])
        recommendation = "REJECT" if fraud_probability >= 80 else (
            "MANUAL_REVIEW" if fraud_probability >= 55 else "APPROVE"
        )

        return {
            "is_fraud": is_fraud,
            "is_fraudulent": is_fraud,
            "fraud_probability": round(fraud_probability, 2),
            "anomaly_score": round(fraud_probability, 2),
            "risk_level": prediction["risk_level"],
            "confidence": float(prediction["confidence"]),
            "recommendation": recommendation,
            "automated_decision_allowed": True,
            "decision_constraints": [],
            "mode": "model",
        }


class AnomalyDetector:
    """
    Anomaly detection for fraud using Isolation Forest.
    
    Academic Note:
    --------------
    Unsupervised approach:
    - Detects outliers without labeled data
    - Useful for new fraud patterns
    - Complements supervised classifier
    """
    
    def __init__(self, contamination: float = 0.1):
        """
        Initialize anomaly detector.
        
        Args:
            contamination: Expected proportion of outliers (0.1 = 10%)
        """
        from sklearn.ensemble import IsolationForest
        
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
    
    def fit(self, X: np.ndarray):
        """
        Fit anomaly detector on normal data.
        
        Args:
            X: Feature matrix (should be mostly legitimate documents)
        """
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        
        logger.info(f"Anomaly detector fitted on {len(X)} samples")
    
    def detect(self, features: np.ndarray) -> Dict:
        """
        Detect if document is anomalous.
        
        Returns:
            {
                'is_anomaly': bool,
                'anomaly_score': float,
                'severity': str
            }
        """
        if features.ndim == 1:
            features = features.reshape(1, -1)
        
        features_scaled = self.scaler.transform(features)
        
        # Predict (-1 = anomaly, 1 = normal)
        prediction = self.model.predict(features_scaled)[0]
        
        # Get anomaly score (lower = more anomalous)
        score = self.model.score_samples(features_scaled)[0]
        
        # Normalize score to 0-100 (higher = more anomalous)
        # Typical range is around -0.5 to 0.5
        normalized_score = max(0, min(100, (0.5 - score) * 100))
        
        # Determine severity
        if normalized_score < 30:
            severity = 'low'
        elif normalized_score < 60:
            severity = 'medium'
        else:
            severity = 'high'
        
        return {
            'is_anomaly': prediction == -1,
            'anomaly_score': round(normalized_score, 2),
            'severity': severity
        }


# Django integration
def detect_fraud(document_id: int) -> Dict:
    """
    Detect fraud for Django Document model.
    
    Usage:
    ```python
    from ai_ml_services.fraud.fraud_detector import detect_fraud
    
    result = detect_fraud(document.id)
    ```
    """
    from apps.applications.models import Document, VerificationResult
    from ai_ml_services.fraud.feature_extractor import DocumentFeatureExtractor
    from django.conf import settings
    
    # Get document
    document = Document.objects.get(id=document_id)
    
    # Extract features
    extractor = DocumentFeatureExtractor()
    features = extractor.extract_features(document)
    
    # Load trained model
    model_path = settings.MODEL_PATH / 'fraud_classifier.pkl'
    detector = FraudDetector(model_path=str(model_path))
    
    # Predict
    result = detector.explain_prediction(features)
    
    # Save to database
    verification_result, created = VerificationResult.objects.get_or_create(
        document=document
    )
    
    verification_result.fraud_risk_score = result['prediction']['fraud_probability']
    verification_result.fraud_prediction = result['prediction']['risk_level']
    verification_result.fraud_indicators = [
        ind['feature'] for ind in result['top_indicators']
    ]
    verification_result.save()
    
    logger.info(f"Fraud detection complete for document {document_id}")
    
    return result


if __name__ == "__main__":
    # Example training
    from sklearn.datasets import make_classification
    
    # Generate synthetic data
    X, y = make_classification(
        n_samples=1000,
        n_features=50,
        n_informative=30,
        n_redundant=10,
        n_classes=2,
        weights=[0.8, 0.2],  # Imbalanced (80% legitimate, 20% fraud)
        random_state=42
    )
    
    # Train detector
    detector = FraudDetector(model_type='random_forest')
    metrics = detector.train(X, y)
    
    print("Training Metrics:")
    print(f"Accuracy: {metrics['accuracy']:.3f}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall: {metrics['recall']:.3f}")
    print(f"F1: {metrics['f1']:.3f}")
    print(f"AUC: {metrics['auc']:.3f}")
    
    # Test prediction
    test_sample = X[0]
    result = detector.explain_prediction(test_sample)
    print("\nPrediction:")
    print(result['explanation'])

