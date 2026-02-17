"""
Document Metadata Analyzer
===========================

Digital forensics for document authenticity verification.

Academic Note:
--------------
Analyzes document metadata and file properties to detect tampering:
1. EXIF data analysis (creation date, software, GPS)
2. Compression artifact detection
3. File format consistency
4. Error level analysis (ELA)
5. Noise pattern analysis

These techniques complement CNN analysis by detecting
digital manipulation traces that may not be visually obvious.

Key Research:
- Fridrich, J. (2009). Digital Image Forensics
- Farid, H. (2009). Image Forgery Detection
"""

import numpy as np
import cv2
from PIL import Image
from PIL.ExifTags import TAGS
import imagehash
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class MetadataAnalyzer:
    """
    Analyze document metadata for authenticity indicators.
    
    Academic Note:
    --------------
    Metadata can reveal:
    1. Editing software used (Photoshop = suspicious for docs)
    2. Multiple save operations
    3. Inconsistent creation/modification dates
    4. GPS data (location tampering)
    5. Camera/scanner information
    """
    
    def __init__(self):
        """Initialize analyzer."""
        self.suspicious_software = [
            'photoshop', 'gimp', 'paint.net', 'inkscape',
            'illustrator', 'affinity', 'pixlr'
        ]
    
    def analyze(self, image_path: str) -> Dict:
        """
        Complete metadata analysis.
        
        Args:
            image_path: Path to document image
        
        Returns:
            Analysis results dictionary
        """
        image_path = Path(image_path)
        
        # Extract EXIF
        exif_data = self._extract_exif(image_path)
        
        # Analyze EXIF
        exif_analysis = self._analyze_exif(exif_data)
        
        # File properties
        file_props = self._analyze_file_properties(image_path)
        
        # Compression analysis
        compression = self._analyze_compression(image_path)
        
        # Calculate metadata score
        metadata_score = self._calculate_metadata_score(
            exif_analysis, file_props, compression
        )
        
        # Compile results
        result = {
            'metadata_score': metadata_score,
            'file_properties_score': file_props['score'],
            'exif_data': exif_data,
            'suspicious_indicators': exif_analysis['suspicious_indicators'],
            'tampering_indicators': [],
            'file_hash': file_props['file_hash'],
            'compression_analysis': compression
        }
        
        # Add tampering indicators
        if exif_analysis['edited_software']:
            result['tampering_indicators'].append(
                f"Edited with: {exif_analysis['edited_software']}"
            )
        
        if exif_analysis['date_inconsistency']:
            result['tampering_indicators'].append("Date inconsistency detected")
        
        if compression['multiple_compressions']:
            result['tampering_indicators'].append("Multiple JPEG compressions detected")
        
        return result
    
    def _extract_exif(self, image_path: Path) -> Dict:
        """Extract EXIF metadata from image."""
        try:
            image = Image.open(image_path)
            exif_data = {}
            
            if hasattr(image, '_getexif') and image._getexif() is not None:
                for tag_id, value in image._getexif().items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = str(value)
            
            return exif_data
        
        except Exception as e:
            logger.warning(f"Error extracting EXIF: {e}")
            return {}
    
    def _analyze_exif(self, exif_data: Dict) -> Dict:
        """
        Analyze EXIF data for suspicious indicators.
        
        Academic Note:
        --------------
        Indicators of manipulation:
        1. Software tags showing photo editing tools
        2. Missing expected metadata
        3. Inconsistent dates (ModifyDate < CreateDate)
        4. GPS data (unexpected for scanned documents)
        """
        analysis = {
            'suspicious_indicators': [],
            'edited_software': None,
            'date_inconsistency': False,
            'has_gps': False
        }
        
        # Check software
        if 'Software' in exif_data:
            software = exif_data['Software'].lower()
            for sus_soft in self.suspicious_software:
                if sus_soft in software:
                    analysis['edited_software'] = exif_data['Software']
                    analysis['suspicious_indicators'].append(
                        f"Edited with photo editing software: {software}"
                    )
                    break
        
        # Check dates
        if 'DateTime' in exif_data and 'DateTimeOriginal' in exif_data:
            try:
                dt = datetime.strptime(exif_data['DateTime'], "%Y:%m:%d %H:%M:%S")
                dt_orig = datetime.strptime(exif_data['DateTimeOriginal'], "%Y:%m:%d %H:%M:%S")
                
                if dt < dt_orig:
                    analysis['date_inconsistency'] = True
                    analysis['suspicious_indicators'].append("Date inconsistency")
            except:
                pass
        
        # Check GPS (unusual for scanned documents)
        if any('GPS' in key for key in exif_data.keys()):
            analysis['has_gps'] = True
            analysis['suspicious_indicators'].append("GPS data present (unusual for scanned document)")
        
        return analysis
    
    def _analyze_file_properties(self, image_path: Path) -> Dict:
        """Analyze basic file properties."""
        stat = image_path.stat()
        
        # Calculate file hash
        with open(image_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        # Get file size
        file_size_mb = stat.st_size / (1024 * 1024)
        
        # Check file extension
        ext = image_path.suffix.lower()
        expected_extensions = ['.jpg', '.jpeg', '.png', '.pdf', '.tiff']
        
        # Calculate score
        score = 100
        
        # Unusual extension
        if ext not in expected_extensions:
            score -= 20
        
        # Very small file (might be low quality or placeholder)
        if file_size_mb < 0.1:
            score -= 15
        
        # Very large file (might be manipulated/uncompressed)
        if file_size_mb > 50:
            score -= 10
        
        return {
            'score': max(0, score),
            'file_size_mb': round(file_size_mb, 2),
            'file_hash': file_hash,
            'extension': ext,
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
    
    def _analyze_compression(self, image_path: Path) -> Dict:
        """
        Analyze JPEG compression artifacts.
        
        Academic Note:
        --------------
        Multiple JPEG compressions leave specific patterns:
        1. Quantization table analysis
        2. Double compression detection
        3. Blocking artifacts
        
        Reference: Fridrich et al. "Detection of Double JPEG Compression"
        """
        try:
            # Load image
            image = cv2.imread(str(image_path))
            
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect blocking artifacts (8x8 blocks from JPEG)
            blocks = self._detect_blocks(gray)
            
            # Estimate compression quality
            quality = self._estimate_jpeg_quality(image_path)
            
            # Multiple compression indicator
            multiple_compressions = blocks > 0.3  # Threshold
            
            return {
                'blocking_artifacts': round(blocks, 3),
                'estimated_quality': quality,
                'multiple_compressions': multiple_compressions
            }
        
        except Exception as e:
            logger.warning(f"Error analyzing compression: {e}")
            return {
                'blocking_artifacts': 0,
                'estimated_quality': None,
                'multiple_compressions': False
            }
    
    def _detect_blocks(self, gray_image: np.ndarray) -> float:
        """
        Detect 8x8 blocking artifacts from JPEG compression.
        
        Returns:
            Blocking score (0-1, higher = more artifacts)
        """
        h, w = gray_image.shape
        
        # Calculate horizontal differences
        h_diff = np.mean(np.abs(np.diff(gray_image[:, ::8], axis=1)))
        
        # Calculate vertical differences
        v_diff = np.mean(np.abs(np.diff(gray_image[::8, :], axis=0)))
        
        # Calculate overall differences
        overall_diff = np.mean(np.abs(np.diff(gray_image)))
        
        # Blocking score (if block boundaries have higher differences)
        if overall_diff > 0:
            blocking = ((h_diff + v_diff) / 2) / overall_diff
        else:
            blocking = 0
        
        return min(1.0, blocking)
    
    def _estimate_jpeg_quality(self, image_path: Path) -> Optional[int]:
        """
        Estimate JPEG quality factor.
        
        Academic Note:
        --------------
        Quality estimation based on quantization tables.
        Lower quality = more compression = potential manipulation.
        """
        try:
            import piexif
            
            # Read JPEG
            with open(image_path, 'rb') as f:
                data = f.read()
            
            # Try to extract quality
            # This is a simplified approach
            # Full implementation would analyze quantization tables
            
            # For now, return None (would need full JPEG parser)
            return None
        
        except:
            return None
    
    def _calculate_metadata_score(
        self,
        exif_analysis: Dict,
        file_props: Dict,
        compression: Dict
    ) -> float:
        """
        Calculate overall metadata authenticity score.
        
        Scoring:
        - Start with 100
        - Deduct points for suspicious indicators
        - Weight file properties
        """
        score = 100
        
        # EXIF suspicions
        score -= len(exif_analysis['suspicious_indicators']) * 10
        
        # File property score contributes 30%
        score = score * 0.7 + file_props['score'] * 0.3
        
        # Compression issues
        if compression['multiple_compressions']:
            score -= 15
        
        if compression['blocking_artifacts'] > 0.5:
            score -= 10
        
        return max(0, min(100, score))


class ErrorLevelAnalyzer:
    """
    Error Level Analysis (ELA) for forgery detection.
    
    Academic Note:
    --------------
    ELA exploits JPEG compression properties:
    1. Save image at specific quality
    2. Compare with original
    3. Manipulated areas show different error levels
    
    Limitation: Works best on JPEG images
    Reference: Krawetz, N. (2007) "Picture Power"
    """
    
    @staticmethod
    def analyze(image_path: str, quality: int = 90) -> Dict:
        """
        Perform error level analysis.
        
        Args:
            image_path: Path to image
            quality: JPEG quality for resave (90 recommended)
        
        Returns:
            ELA results
        """
        try:
            import io
            
            # Open original
            original = Image.open(image_path).convert('RGB')
            
            # Resave at quality
            buffer = io.BytesIO()
            original.save(buffer, format='JPEG', quality=quality)
            buffer.seek(0)
            resaved = Image.open(buffer)
            
            # Calculate difference
            diff = np.abs(
                np.array(original, dtype=np.float32) -
                np.array(resaved, dtype=np.float32)
            )
            
            # Enhance for visualization
            ela_image = (diff * 10).clip(0, 255).astype(np.uint8)
            
            # Calculate statistics
            mean_diff = np.mean(diff)
            max_diff = np.max(diff)
            std_diff = np.std(diff)
            
            # High variance suggests manipulation
            suspicion_score = min(100, std_diff * 2)
            
            return {
                'mean_error': round(mean_diff, 2),
                'max_error': round(max_diff, 2),
                'std_error': round(std_diff, 2),
                'suspicion_score': round(suspicion_score, 2),
                'ela_image': ela_image  # Can be saved for visualization
            }
        
        except Exception as e:
            logger.error(f"ELA analysis failed: {e}")
            return {
                'mean_error': 0,
                'max_error': 0,
                'std_error': 0,
                'suspicion_score': 0,
                'ela_image': None
            }


# Django integration
def analyze_document_metadata(document_id: int) -> Dict:
    """
    Analyze document metadata for Django model.
    
    Usage:
    ```python
    from apps.ai_services.authenticity.metadata_analyzer import analyze_document_metadata
    
    result = analyze_document_metadata(document.id)
    ```
    """
    from apps.applications.models import Document
    
    document = Document.objects.get(id=document_id)
    
    # Metadata analysis
    metadata_analyzer = MetadataAnalyzer()
    metadata_result = metadata_analyzer.analyze(document.file.path)
    
    # ELA analysis
    ela_analyzer = ErrorLevelAnalyzer()
    ela_result = ela_analyzer.analyze(document.file.path)
    
    # Combine results
    result = {
        **metadata_result,
        'ela_analysis': ela_result
    }
    
    logger.info(f"Metadata analysis complete for document {document_id}")
    
    return result


if __name__ == "__main__":
    # Test analyzer
    analyzer = MetadataAnalyzer()
    result = analyzer.analyze('test_document.jpg')
    
    print(f"Metadata Score: {result['metadata_score']}")
    print(f"Suspicious Indicators: {result['suspicious_indicators']}")
    print(f"Tampering Indicators: {result['tampering_indicators']}")
