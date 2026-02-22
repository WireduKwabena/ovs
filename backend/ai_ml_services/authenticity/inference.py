"""
Document Authenticity Detection - Inference Module
===================================================

Production-ready inference for document authenticity detection.

Academic Note:
--------------
This module provides:
1. Single image prediction
2. Batch prediction
3. Test-time augmentation
4. Confidence calibration
5. Integration with Django ORM

Usage in Django:
```python
from ai_ml_services.authenticity.inference import AuthenticityDetector

detector = AuthenticityDetector(model_path='models/authenticity_cnn.pth')
result = detector.predict('path/to/document.jpg')
print(f"Authenticity score: {result['authenticity_score']}")
```
"""

import torch
import torch.nn as nn
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging
import time

from .cnn_detector import create_model, DocumentTransforms

logger = logging.getLogger(__name__)


def _safe_torch_load(model_path: Path, map_location: str):
    """Load checkpoint preferring safer weights-only deserialization."""
    try:
        return torch.load(model_path, map_location=map_location, weights_only=True)
    except TypeError:
        logger.warning(
            "torch.load(weights_only=True) is not supported in this torch version; "
            "falling back to legacy deserialization for %s",
            model_path,
        )
        return torch.load(model_path, map_location=map_location)


class AuthenticityDetector:
    """
    Production inference class for document authenticity detection.
    
    Academic Note:
    --------------
    Features:
    1. Model loading with error handling
    2. Efficient batch processing
    3. Test-time augmentation for robustness
    4. Confidence calibration
    5. GPU acceleration with fallback to CPU
    """
    
    def __init__(
        self,
        model_path: str,
        device: Optional[str] = None,
        use_tta: bool = False,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize detector.
        
        Args:
            model_path: Path to trained model checkpoint
            device: Device to run on ('cuda' or 'cpu', auto-detect if None)
            use_tta: Use test-time augmentation
            confidence_threshold: Minimum confidence for high-confidence predictions
        """
        self.model_path = Path(model_path)
        self.use_tta = use_tta
        self.confidence_threshold = confidence_threshold
        
        # Device setup
        if device is None:
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        logger.info(f"Initializing AuthenticityDetector on {self.device}")
        
        # Load model
        self.model = self._load_model()
        self.model.eval()
        
        # Transforms
        self.transform = DocumentTransforms.get_val_transforms()
        if use_tta:
            self.tta_transforms = DocumentTransforms.get_tta_transforms()
    
    def _load_model(self) -> nn.Module:
        """Load trained model from checkpoint."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {self.model_path}")
        
        # Create model
        model = create_model('resnet18', pretrained=False)
        
        # Load checkpoint
        checkpoint = _safe_torch_load(self.model_path, map_location=self.device)
        
        # Load state dict
        if 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
            logger.info(f"Loaded model from epoch {checkpoint.get('epoch', 'unknown')}")
            logger.info(f"Best metrics: {checkpoint.get('metrics', {})}")
        else:
            model.load_state_dict(checkpoint)
        
        model = model.to(self.device)
        model.eval()
        
        return model
    
    def predict(
        self,
        image_path: Union[str, Path],
        return_features: bool = False
    ) -> Dict:
        """
        Predict authenticity for a single document.
        
        Args:
            image_path: Path to document image
            return_features: Also return feature embeddings
        
        Returns:
            Dictionary with prediction results:
            {
                'authenticity_score': float (0-100),
                'is_authentic': bool,
                'confidence': float (0-100),
                'prediction_time_ms': float,
                'features': Optional[np.ndarray]
            }
        """
        start_time = time.time()
        
        # Load and preprocess image
        image = Image.open(image_path).convert('RGB')
        image_tensor = self.transform(image).unsqueeze(0).to(self.device)
        
        # Predict
        with torch.no_grad():
            if self.use_tta:
                # Test-time augmentation
                predictions = []
                for tta_transform in self.tta_transforms:
                    aug_tensor = tta_transform(Image.open(image_path).convert('RGB'))
                    aug_tensor = aug_tensor.unsqueeze(0).to(self.device)
                    output = self.model(aug_tensor)
                    predictions.append(output.item())
                
                # Average predictions
                authenticity_prob = np.mean(predictions)
                confidence = 100 - (np.std(predictions) * 100)  # Lower std = higher confidence
            else:
                output = self.model(image_tensor)
                authenticity_prob = output.item()
                confidence = self._calculate_confidence(authenticity_prob)
            
            # Extract features if requested
            features = None
            if return_features:
                features = self.model.extract_features(image_tensor)
                features = features.cpu().numpy()
        
        # Convert to percentage
        authenticity_score = authenticity_prob * 100
        
        # Determine if authentic
        is_authentic = authenticity_prob > 0.5
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # milliseconds
        
        result = {
            'authenticity_score': round(authenticity_score, 2),
            'is_authentic': is_authentic,
            'confidence': round(confidence, 2),
            'prediction_time_ms': round(processing_time, 2)
        }
        
        if return_features:
            result['features'] = features
        
        return result
    
    def predict_batch(
        self,
        image_paths: List[Union[str, Path]],
        batch_size: int = 32
    ) -> List[Dict]:
        """
        Predict authenticity for multiple documents.
        
        Args:
            image_paths: List of image paths
            batch_size: Batch size for processing
        
        Returns:
            List of prediction dictionaries
        """
        results = []
        
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i+batch_size]
            
            # Load and transform images
            images = []
            for path in batch_paths:
                image = Image.open(path).convert('RGB')
                image_tensor = self.transform(image)
                images.append(image_tensor)
            
            # Stack into batch
            batch_tensor = torch.stack(images).to(self.device)
            
            # Predict
            with torch.no_grad():
                outputs = self.model(batch_tensor)
                probabilities = outputs.cpu().numpy().flatten()
            
            # Process results
            for prob in probabilities:
                authenticity_score = prob * 100
                is_authentic = prob > 0.5
                confidence = self._calculate_confidence(prob)
                
                results.append({
                    'authenticity_score': round(authenticity_score, 2),
                    'is_authentic': is_authentic,
                    'confidence': round(confidence, 2)
                })
        
        return results
    
    def _calculate_confidence(self, probability: float) -> float:
        """
        Calculate confidence score from probability.
        
        Academic Note:
        --------------
        Confidence is higher when probability is far from 0.5 (decision boundary).
        
        Formula: confidence = |probability - 0.5| * 200
        
        - prob = 0.5 → confidence = 0 (uncertain)
        - prob = 1.0 → confidence = 100 (very confident)
        - prob = 0.0 → confidence = 100 (very confident)
        """
        return abs(probability - 0.5) * 200
    
    def get_model_info(self) -> Dict:
        """Get information about loaded model."""
        total_params = sum(p.numel() for p in self.model.parameters())
        trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        
        return {
            'model_path': str(self.model_path),
            'device': self.device,
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'use_tta': self.use_tta,
            'confidence_threshold': self.confidence_threshold
        }


class DocumentAuthenticityService:
    """
    High-level service for document authenticity checking.
    
    Combines CNN predictions with metadata analysis for robust detection.
    
    Academic Note:
    --------------
    Ensemble approach:
    1. CNN visual analysis (70% weight)
    2. Metadata analysis (20% weight)
    3. File property analysis (10% weight)
    
    Final score is weighted average of all components.
    """
    
    def __init__(
        self,
        cnn_model_path: str,
        device: Optional[str] = None
    ):
        """
        Initialize service.
        
        Args:
            cnn_model_path: Path to CNN model
            device: Computing device
        """
        # CNN detector
        self.cnn_detector = AuthenticityDetector(
            model_path=cnn_model_path,
            device=device,
            use_tta=True
        )
        
        # Metadata analyzer
        from .metadata_analyzer import ForensicAnalyzer
        self.metadata_analyzer = ForensicAnalyzer()
    
    def analyze_document(self, image_path: Union[str, Path]) -> Dict:
        """
        Complete document authenticity analysis.
        
        Args:
            image_path: Path to document image
        
        Returns:
            Comprehensive analysis results
        """
        logger.info(f"Analyzing document: {image_path}")
        
        # CNN analysis
        cnn_result = self.cnn_detector.predict(image_path)
        
        # Metadata analysis
        metadata_result = self.metadata_analyzer.analyze(image_path)
        
        # Combine results (weighted average)
        weights = {
            'cnn': 0.70,
            'metadata': 0.30,
        }
        metadata_score = float(metadata_result.get('final_score', 50.0))
        
        overall_score = (
            cnn_result['authenticity_score'] * weights['cnn'] +
            metadata_score * weights['metadata']
        )
        
        # Determine final verdict
        is_authentic = overall_score >= 70  # Threshold for authenticity
        
        # Compile detailed results
        result = {
            'overall_authenticity_score': round(overall_score, 2),
            'is_authentic': is_authentic,
            'confidence': round(cnn_result['confidence'], 2),
            'cnn_analysis': cnn_result,
            'metadata_analysis': metadata_result,
            'weights_used': weights,
            'red_flags': [],
            'recommendations': []
        }
        
        # Add red flags
        if cnn_result['authenticity_score'] < 50:
            result['red_flags'].append('Low CNN authenticity score')
        
        if metadata_result['tampering_indicators']:
            result['red_flags'].extend(metadata_result['tampering_indicators'])
        
        # Add recommendations
        if overall_score < 70:
            result['recommendations'].append('Manual review recommended')
        
        if cnn_result['confidence'] < 50:
            result['recommendations'].append('Low confidence - request higher quality scan')
        
        return result


# Django integration functions
def analyze_document_for_django(document_id: int) -> Dict:
    """
    Analyze document authenticity for Django model.
    
    Usage in Django views/tasks:
    ```python
    from ai_ml_services.authenticity.inference import analyze_document_for_django
    
    result = analyze_document_for_django(document.id)
    ```
    """
    from apps.applications.models import Document, VerificationResult
    from django.conf import settings
    
    # Get document
    document = Document.objects.get(id=document_id)
    
    # Initialize service
    model_path = settings.MODEL_PATH / 'authenticity_detector.pth'
    service = DocumentAuthenticityService(cnn_model_path=str(model_path))
    
    # Analyze
    result = service.analyze_document(document.file.path)
    
    # Save results (update if exists, create if not)
    verification_result, created = VerificationResult.objects.update_or_create(
        document=document,
        defaults={
            'authenticity_score': result['overall_authenticity_score'],
            'authenticity_confidence': result['confidence'],
            'is_authentic': result['is_authentic'],
            'detailed_results': result
        }
    )
    
    logger.info(f"Document {document_id} analysis complete. Score: {result['overall_authenticity_score']}")
    
    return result


if __name__ == "__main__":
    # Test inference
    detector = AuthenticityDetector(
        model_path='models/checkpoints/best_model.pth',
        use_tta=True
    )
    
    # Single prediction
    result = detector.predict('test_document.jpg')
    print(f"Authenticity Score: {result['authenticity_score']}")
    print(f"Is Authentic: {result['is_authentic']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Processing Time: {result['prediction_time_ms']} ms")

