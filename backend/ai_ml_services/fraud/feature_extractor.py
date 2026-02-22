"""
Document Feature Extractor
===========================

Extract features from documents for fraud detection.

Academic Note:
--------------
Feature engineering is crucial for ML performance:
1. Metadata features (file properties, EXIF)
2. Content features (text patterns, OCR quality)
3. Statistical features (character distribution, entropy)
4. Behavioral features (submission patterns)

Goal: Create discriminative features that separate legitimate from fraudulent documents.
"""

import numpy as np
import cv2
from PIL import Image
from PIL.ExifTags import TAGS
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentFeatureExtractor:
    """
    Extract comprehensive features for fraud detection.
    
    Feature Categories:
    1. File Metadata (15 features)
    2. Image Properties (10 features)
    3. Content Features (15 features)
    4. Statistical Features (10 features)
    
    Total: ~50 features
    """
    
    def __init__(self):
        """Initialize feature extractor."""
        self.feature_names = self._get_feature_names()
    
    def extract_features(self, document) -> np.ndarray:
        """
        Extract all features from Django Document model.
        
        Args:
            document: Django Document instance
        
        Returns:
            Feature vector (numpy array)
        """
        features = {}
        
        # Load image
        image_path = document.file.path
        image = cv2.imread(str(image_path))
        
        # 1. File Metadata Features
        features.update(self._extract_file_features(image_path))
        
        # 2. Image Property Features
        features.update(self._extract_image_features(image))
        
        # 3. Content Features (if OCR available)
        if document.extracted_text:
            features.update(self._extract_content_features(document.extracted_text))
        else:
            # Placeholder zeros
            features.update({f'content_{i}': 0 for i in range(15)})
        
        # 4. Statistical Features
        features.update(self._extract_statistical_features(image))
        
        # 5. Authenticity Features (if available)
        if hasattr(document, 'verification_result'):
            features.update(self._extract_authenticity_features(document.verification_result))
        else:
            features.update({f'auth_{i}': 0 for i in range(5)})
        
        # Convert to numpy array (maintain order)
        feature_vector = np.array([
            features[name] for name in self.feature_names
        ])
        
        logger.info(f"Extracted {len(feature_vector)} features from document {document.id}")
        
        return feature_vector
    
    def extract_features_from_path(self, image_path: str, ocr_text: str = None) -> np.ndarray:
        """
        Extract features from file path (without Django).
        
        Args:
            image_path: Path to image
            ocr_text: Optional OCR text
        
        Returns:
            Feature vector
        """
        features = {}
        
        image = cv2.imread(str(image_path))
        
        features.update(self._extract_file_features(image_path))
        features.update(self._extract_image_features(image))
        
        if ocr_text:
            features.update(self._extract_content_features(ocr_text))
        else:
            features.update({f'content_{i}': 0 for i in range(15)})
        
        features.update(self._extract_statistical_features(image))
        features.update({f'auth_{i}': 0 for i in range(5)})  # Placeholder
        
        feature_vector = np.array([
            features[name] for name in self.feature_names
        ])
        
        return feature_vector
    
    def _extract_file_features(self, image_path: str) -> Dict:
        """
        Extract file metadata features.
        
        Features:
        - File size (normalized)
        - File extension (encoded)
        - Creation/modification dates
        - EXIF data presence
        - Hash-based features
        """
        path = Path(image_path)
        stat = path.stat()
        
        features = {}
        
        # File size (in MB, log-scaled)
        file_size_mb = stat.st_size / (1024 * 1024)
        features['file_size_log'] = np.log1p(file_size_mb)
        
        # File extension (one-hot)
        ext = path.suffix.lower()
        features['ext_jpg'] = 1 if ext in ['.jpg', '.jpeg'] else 0
        features['ext_png'] = 1 if ext == '.png' else 0
        features['ext_pdf'] = 1 if ext == '.pdf' else 0
        features['ext_tiff'] = 1 if ext in ['.tiff', '.tif'] else 0
        
        # Time features
        created = datetime.fromtimestamp(stat.st_ctime)
        modified = datetime.fromtimestamp(stat.st_mtime)
        
        features['days_since_creation'] = (datetime.now() - created).days
        features['creation_modified_diff'] = (modified - created).total_seconds() / 3600  # hours
        
        # EXIF features
        exif_features = self._extract_exif_features(image_path)
        features.update(exif_features)
        
        # Hash features (file uniqueness indicators)
        with open(image_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        features['hash_entropy'] = self._calculate_entropy(file_hash)
        
        return features
    
    def _extract_exif_features(self, image_path: str) -> Dict:
        """Extract EXIF metadata features."""
        features = {
            'has_exif': 0,
            'has_gps': 0,
            'has_software': 0,
            'exif_fields_count': 0,
            'suspicious_software': 0
        }
        
        try:
            image = Image.open(image_path)
            if hasattr(image, '_getexif') and image._getexif():
                exif = image._getexif()
                features['has_exif'] = 1
                features['exif_fields_count'] = len(exif)
                
                # Check for GPS
                if any('GPS' in TAGS.get(tag, '') for tag in exif.keys()):
                    features['has_gps'] = 1
                
                # Check for software tag
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == 'Software':
                        features['has_software'] = 1
                        # Check if editing software
                        software_lower = str(value).lower()
                        suspicious = ['photoshop', 'gimp', 'paint', 'illustrator']
                        if any(sus in software_lower for sus in suspicious):
                            features['suspicious_software'] = 1
        except:
            pass
        
        return features
    
    def _extract_image_features(self, image: np.ndarray) -> Dict:
        """
        Extract image property features.
        
        Features:
        - Dimensions
        - Aspect ratio
        - Color distribution
        - Brightness/contrast
        - Noise level
        """
        h, w = image.shape[:2]
        
        features = {}
        
        # Dimensions (log-scaled)
        features['width_log'] = np.log1p(w)
        features['height_log'] = np.log1p(h)
        features['aspect_ratio'] = w / h if h > 0 else 1.0
        
        # Color features
        if len(image.shape) == 3:
            # Color image
            features['is_grayscale'] = 0
            
            # Average per channel
            features['avg_blue'] = np.mean(image[:, :, 0]) / 255
            features['avg_green'] = np.mean(image[:, :, 1]) / 255
            features['avg_red'] = np.mean(image[:, :, 2]) / 255
        else:
            features['is_grayscale'] = 1
            features['avg_blue'] = 0
            features['avg_green'] = 0
            features['avg_red'] = 0
        
        # Brightness and contrast
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        features['brightness'] = np.mean(gray) / 255
        features['contrast'] = np.std(gray) / 255
        
        # Noise estimation (using Laplacian)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        features['noise_level'] = np.log1p(laplacian_var)
        
        return features
    
    def _extract_content_features(self, text: str) -> Dict:
        """
        Extract content/text features.
        
        Features:
        - Text length
        - Character distribution
        - Word patterns
        - Special characters
        - Suspicious patterns
        """
        features = {}
        
        # Basic text stats
        features['text_length'] = len(text)
        features['word_count'] = len(text.split())
        features['char_count'] = len(text)
        features['avg_word_length'] = features['char_count'] / max(1, features['word_count'])
        
        # Character type distribution
        features['uppercase_ratio'] = sum(1 for c in text if c.isupper()) / max(1, len(text))
        features['lowercase_ratio'] = sum(1 for c in text if c.islower()) / max(1, len(text))
        features['digit_ratio'] = sum(1 for c in text if c.isdigit()) / max(1, len(text))
        features['special_char_ratio'] = sum(1 for c in text if not c.isalnum()) / max(1, len(text))
        
        # Whitespace
        features['whitespace_ratio'] = sum(1 for c in text if c.isspace()) / max(1, len(text))
        
        # Pattern features
        features['has_email'] = 1 if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text) else 0
        features['has_phone'] = 1 if re.search(r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}', text) else 0
        features['has_date'] = 1 if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text) else 0
        features['has_id_pattern'] = 1 if re.search(r'\b[A-Z0-9]{6,}\b', text) else 0
        
        # Suspicious patterns (repeated text, Lorem ipsum, etc.)
        words = text.split()
        if words:
            word_counts = Counter(words)
            most_common_count = word_counts.most_common(1)[0][1] if word_counts else 0
            features['repetition_score'] = most_common_count / len(words)
        else:
            features['repetition_score'] = 0
        
        features['has_lorem'] = 1 if 'lorem ipsum' in text.lower() else 0
        
        return features
    
    def _extract_statistical_features(self, image: np.ndarray) -> Dict:
        """
        Extract statistical features.
        
        Features:
        - Pixel intensity distribution
        - Entropy
        - Edge density
        - Texture features
        """
        features = {}
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        
        # Histogram features
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()  # Normalize
        
        # Entropy
        entropy = -np.sum(hist * np.log2(hist + 1e-10))
        features['pixel_entropy'] = entropy / 8  # Normalize to 0-1
        
        # Statistical moments
        features['pixel_mean'] = np.mean(gray) / 255
        features['pixel_std'] = np.std(gray) / 255
        features['pixel_skewness'] = self._calculate_skewness(gray)
        features['pixel_kurtosis'] = self._calculate_kurtosis(gray)
        
        # Edge detection
        edges = cv2.Canny(gray, 50, 150)
        features['edge_density'] = np.sum(edges > 0) / edges.size
        
        # Texture (using Local Binary Patterns approximation)
        features['texture_score'] = self._calculate_texture_score(gray)
        
        # JPEG compression artifacts (block detection)
        features['blocking_artifacts'] = self._detect_blocking(gray)
        
        # Color coherence (if color image)
        if len(image.shape) == 3:
            features['color_coherence'] = self._calculate_color_coherence(image)
        else:
            features['color_coherence'] = 0
        
        return features
    
    def _extract_authenticity_features(self, verification_result) -> Dict:
        """Extract features from CNN authenticity analysis."""
        features = {}
        
        if verification_result:
            features['auth_score'] = verification_result.authenticity_score / 100
            features['auth_confidence'] = verification_result.authenticity_confidence / 100
            features['metadata_check'] = 1 if verification_result.metadata_check_passed else 0
            features['visual_check'] = 1 if verification_result.visual_check_passed else 0
            features['tampering_detected'] = 1 if verification_result.tampering_detected else 0
        else:
            features = {f'auth_{i}': 0 for i in range(5)}
        
        return features
    
    def _calculate_entropy(self, data: str) -> float:
        """Calculate Shannon entropy of string."""
        counter = Counter(data)
        total = len(data)
        entropy = -sum(
            (count / total) * np.log2(count / total)
            for count in counter.values()
        )
        return entropy
    
    def _calculate_skewness(self, data: np.ndarray) -> float:
        """Calculate skewness of pixel distribution."""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0
        return np.mean(((data - mean) / std) ** 3)
    
    def _calculate_kurtosis(self, data: np.ndarray) -> float:
        """Calculate kurtosis of pixel distribution."""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            return 0
        return np.mean(((data - mean) / std) ** 4) - 3
    
    def _calculate_texture_score(self, gray: np.ndarray) -> float:
        """Calculate texture complexity score."""
        # Simplified texture measure using gradient magnitude
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = np.sqrt(gx**2 + gy**2)
        return np.mean(magnitude) / 255
    
    def _detect_blocking(self, gray: np.ndarray) -> float:
        """
        Detect 8x8 blocking artifacts (JPEG compression).
        
        Returns:
            Blocking score (0-1, higher = more artifacts)
        """
        h, w = gray.shape
        
        # Calculate differences at block boundaries
        h_diff = np.mean(np.abs(np.diff(gray[:, ::8], axis=1)))
        v_diff = np.mean(np.abs(np.diff(gray[::8, :], axis=0)))
        
        # Compare with overall differences
        overall_diff = np.mean(np.abs(np.diff(gray)))
        
        if overall_diff > 0:
            blocking = ((h_diff + v_diff) / 2) / overall_diff
        else:
            blocking = 0
        
        return min(1.0, blocking)
    
    def _calculate_color_coherence(self, image: np.ndarray) -> float:
        """Calculate color coherence (how uniform colors are)."""
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        
        # Calculate standard deviation per channel
        std_l = np.std(lab[:, :, 0])
        std_a = np.std(lab[:, :, 1])
        std_b = np.std(lab[:, :, 2])
        
        # Average std (lower = more coherent)
        avg_std = (std_l + std_a + std_b) / 3
        
        # Normalize to 0-1 (inverse, so higher = more coherent)
        coherence = 1 - min(1.0, avg_std / 100)
        
        return coherence
    
    def _get_feature_names(self) -> List[str]:
        """Get ordered list of all feature names."""
        names = []
        
        # File features (15)
        names.extend([
            'file_size_log', 'ext_jpg', 'ext_png', 'ext_pdf', 'ext_tiff',
            'days_since_creation', 'creation_modified_diff',
            'has_exif', 'has_gps', 'has_software', 'exif_fields_count',
            'suspicious_software', 'hash_entropy'
        ])
        
        # Image features (10)
        names.extend([
            'width_log', 'height_log', 'aspect_ratio', 'is_grayscale',
            'avg_blue', 'avg_green', 'avg_red',
            'brightness', 'contrast', 'noise_level'
        ])
        
        # Content features (15)
        names.extend([
            'text_length', 'word_count', 'char_count', 'avg_word_length',
            'uppercase_ratio', 'lowercase_ratio', 'digit_ratio',
            'special_char_ratio', 'whitespace_ratio',
            'has_email', 'has_phone', 'has_date', 'has_id_pattern',
            'repetition_score', 'has_lorem'
        ])
        
        # Statistical features (10)
        names.extend([
            'pixel_entropy', 'pixel_mean', 'pixel_std',
            'pixel_skewness', 'pixel_kurtosis', 'edge_density',
            'texture_score', 'blocking_artifacts', 'color_coherence'
        ])
        
        # Authenticity features (5)
        names.extend([
            'auth_score', 'auth_confidence', 'metadata_check',
            'visual_check', 'tampering_detected'
        ])
        
        return names[:50]  # Limit to 50 features


if __name__ == "__main__":
    # Test feature extraction
    extractor = DocumentFeatureExtractor()
    
    features = extractor.extract_features_from_path(
        'test_document.jpg',
        ocr_text="Sample OCR text from document"
    )
    
    print(f"Extracted {len(features)} features")
    print(f"Feature names: {extractor.feature_names[:10]}...")  # First 10
    print(f"Feature values: {features[:10]}")  # First 10
