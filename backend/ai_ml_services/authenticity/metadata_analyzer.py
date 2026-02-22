"""
Digital Forensics Analyzer for Document Authenticity
=====================================================

This module provides a consolidated suite of traditional computer vision and
metadata analysis techniques to detect digital tampering in documents. It is
designed to complement deep learning-based approaches.

Techniques Implemented:
-----------------------
1.  **EXIF Data Analysis**: Checks for suspicious software tags, date
    inconsistencies, and other metadata anomalies.
2.  **File Property Analysis**: Examines file size, extension, and hashes.
3.  **Copy-Move Forgery Detection**: Uses ORB feature detection to find
    duplicated regions within an image, which is a common sign of manipulation.
    ORB is used as a royalty-free alternative to SIFT.
4.  **Compression Artifact Analysis**: Analyzes JPEG blocking artifacts to
    detect repeated compressions, another indicator of editing.
5.  **Error Level Analysis (ELA)**: Identifies areas of an image with different
    compression levels, which can reveal manipulated regions.

Key Research:
- Fridrich, J. (2009). Digital Image Forensics.
- Farid, H. (2009). Image Forgery Detection.
- Krawetz, N. (2007). "Picture Power" (on ELA).
"""

import hashlib
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

import cv2
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS
import dateutil.parser

logger = logging.getLogger(__name__)


class ForensicAnalyzer:
    """
    Consolidated analyzer for metadata, file properties, and CV-based forgery detection.
    """

    def __init__(self):
        """Initialize the analyzer."""
        self.suspicious_software = [
            'photoshop', 'gimp', 'paint.net', 'inkscape',
            'illustrator', 'affinity', 'pixlr'
        ]

    def analyze(self, image_path: str) -> Dict:
        """
        Run a comprehensive forensic analysis on a single document image.

        Args:
            image_path: Path to the document image.

        Returns:
            A dictionary containing the aggregated analysis results.
        """
        image_path = Path(image_path)
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to read image from {image_path}")

        # 1. EXIF and File Property Analysis
        exif_data = self._extract_exif(image_path)
        exif_analysis = self._analyze_exif(exif_data)
        file_props = self._analyze_file_properties(image_path)

        # 2. CV-based Forgery Detection
        copy_move_result = self.detect_copy_move(image)
        compression_result = self.analyze_compression(image)
        ela_result = self.analyze_error_level(image_path)

        # 3. Aggregate scores
        final_score = self._calculate_final_score(
            exif_analysis, file_props, copy_move_result, compression_result, ela_result
        )

        tampering_indicators = self._collect_tampering_indicators(
            exif_analysis, copy_move_result, compression_result, ela_result
        )

        return {
            'final_score': final_score,
            'is_authentic_guess': final_score >= 70,
            'tampering_indicators': tampering_indicators,
            'exif_analysis': exif_analysis,
            'file_properties': file_props,
            'copy_move_analysis': copy_move_result,
            'compression_analysis': compression_result,
            'ela_analysis': ela_result,
        }

    def _extract_exif(self, image_path: Path) -> Dict:
        """Extract EXIF metadata from an image using the public getexif method."""
        try:
            image = Image.open(image_path)
            exif_data = {}
            # Use the public getexif() method for better compatibility
            raw_exif = image.getexif()
            if raw_exif:
                for tag_id, value in raw_exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = str(value)
            return exif_data
        except Exception as e:
            logger.warning(f"Could not extract EXIF data from {image_path}: {e}")
            return {}

    def _analyze_exif(self, exif_data: Dict) -> Dict:
        """Analyze extracted EXIF data for suspicious indicators."""
        analysis = {
            'suspicious_indicators': [],
            'edited_software': None,
            'date_inconsistency': False,
        }

        # Check for suspicious software
        if 'Software' in exif_data:
            software = exif_data['Software'].lower()
            if any(s in software for s in self.suspicious_software):
                analysis['edited_software'] = exif_data['Software']
                analysis['suspicious_indicators'].append(
                    f"Edited with photo editing software: {analysis['edited_software']}"
                )

        # Check for date inconsistencies
        try:
            if 'DateTime' in exif_data and 'DateTimeOriginal' in exif_data:
                dt_modified = dateutil.parser.parse(exif_data['DateTime'].replace(":", "-", 2))
                dt_original = dateutil.parser.parse(exif_data['DateTimeOriginal'].replace(":", "-", 2))
                if dt_modified != dt_original:
                    analysis['date_inconsistency'] = True
                    analysis['suspicious_indicators'].append("Original creation and modification dates do not match.")
        except (ValueError, TypeError):
            logger.warning("Could not parse EXIF dates for comparison.")

        return analysis

    def _analyze_file_properties(self, image_path: Path) -> Dict:
        """Analyze basic file properties like size and hash."""
        try:
            stat = image_path.stat()
            with open(image_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            file_size_mb = stat.st_size / (1024 * 1024)

            return {
                'file_size_mb': round(file_size_mb, 2),
                'file_hash_sha256': file_hash,
                'extension': image_path.suffix.lower(),
                'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to analyze file properties for {image_path}: {e}")
            return {}

    def detect_copy_move(self, image: np.ndarray, min_match_count: int = 10) -> Dict:
        """
        Detect copy-move forgery using ORB, a royalty-free feature detector.
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            orb = cv2.ORB_create()
            keypoints, descriptors = orb.detectAndCompute(gray, None)

            if descriptors is None or len(descriptors) < min_match_count:
                return {'detected': False, 'confidence': 0, 'reason': 'Insufficient keypoints.'}

            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(descriptors, descriptors)

            # Filter out self-matches and matches that are too close
            good_matches = []
            for match in matches:
                pt1 = keypoints[match.queryIdx].pt
                pt2 = keypoints[match.trainIdx].pt
                if match.queryIdx != match.trainIdx and np.linalg.norm(np.array(pt1) - np.array(pt2)) > 50:
                    good_matches.append(match)
            
            detected = len(good_matches) > min_match_count
            confidence = min((len(good_matches) / (min_match_count * 2)) * 100, 100)

            return {
                'detected': detected,
                'confidence': round(confidence, 2),
                'match_count': len(good_matches),
            }
        except cv2.error as e:
            logger.error(f"Copy-move detection failed with OpenCV error: {e}")
            return {'detected': False, 'confidence': 0, 'error': str(e)}
        except Exception as e:
            logger.error(f"An unexpected error occurred in copy-move detection: {e}")
            return {'detected': False, 'confidence': 0, 'error': str(e)}

    def analyze_compression(self, image: np.ndarray) -> Dict:
        """Analyzes an image for signs of JPEG compression artifacts."""
        try:
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            y_channel = ycrcb[:, :, 0]

            blockiness = self._calculate_blockiness_numpy(y_channel)
            suspicious = blockiness > 1.2  # Adjusted threshold

            return {
                'blockiness_score': round(blockiness, 2),
                'is_suspicious': suspicious,
                'interpretation': 'High blockiness detected, may indicate heavy JPEG compression.' if suspicious else 'Normal blockiness level.'
            }
        except Exception as e:
            logger.error(f"Compression analysis failed: {e}")
            return {'blockiness_score': 0, 'is_suspicious': False, 'error': str(e)}

    def _calculate_blockiness_numpy(self, y_channel: np.ndarray, block_size: int = 8) -> float:
        """
        Calculate a blockiness score using vectorized NumPy operations.
        A higher score indicates more prominent blocking artifacts.
        """
        if y_channel.ndim != 2 or y_channel.size == 0:
            return 0.0

        h, w = y_channel.shape
        y_channel = y_channel.astype(np.float32)

        # Calculate horizontal differences at block boundaries
        h_boundaries = np.abs(y_channel[:, block_size-1:-1:block_size] - y_channel[:, block_size::block_size])
        
        # Calculate vertical differences at block boundaries
        v_boundaries = np.abs(y_channel[block_size-1:-1:block_size, :] - y_channel[block_size::block_size, :])
        
        # Normalize by total number of boundary pixels
        total_pixels = h * w
        if total_pixels == 0: return 0.0
        
        # Sum of differences, normalized
        blockiness = (np.sum(h_boundaries) + np.sum(v_boundaries)) / total_pixels
        return blockiness

    def analyze_error_level(self, image_path: Path, quality: int = 90) -> Dict:
        """
        Performs Error Level Analysis (ELA) to find regions with different
        JPEG compression levels.
        """
        try:
            original = Image.open(image_path).convert('RGB')

            with io.BytesIO() as buffer:
                original.save(buffer, format='JPEG', quality=quality)
                buffer.seek(0)
                resaved = Image.open(buffer)

                diff = np.abs(np.array(original, dtype=np.float32) - np.array(resaved, dtype=np.float32))

            # If difference is negligible, no point analyzing further
            if np.max(diff) < 1e-5:
                return {'mean_error': 0.0, 'suspicion_score': 0.0, 'is_suspicious': False}

            # Scale for visibility and stats
            ela_scaled = (diff / np.max(diff)) * 255.0
            suspicion_score = np.std(ela_scaled) * 2.5 # STD is a good indicator of variance

            return {
                'mean_error': round(np.mean(diff), 2),
                'suspicion_score': round(min(100, suspicion_score), 2),
                'is_suspicious': suspicion_score > 25, # Threshold for suspicion
            }
        except Exception as e:
            logger.error(f"ELA failed for {image_path}: {e}")
            return {'mean_error': 0, 'suspicion_score': 0, 'is_suspicious': False, 'error': str(e)}
    
    def _calculate_final_score(self, *analyses) -> float:
        """Calculate a final, weighted score from all analysis components."""
        # Define weights for each analysis type
        weights = {
            'exif': 0.20,
            'props': 0.10,
            'copy_move': 0.30,
            'compression': 0.20,
            'ela': 0.20,
        }
        
        exif_analysis, file_props, copy_move, compression, ela = analyses
        
        score = 100.0
        
        # Deductions from EXIF
        score -= len(exif_analysis.get('suspicious_indicators', [])) * 15
        
        # Deductions from copy-move
        if copy_move.get('detected', False):
            score -= copy_move.get('confidence', 0) * weights['copy_move']

        # Deductions from compression
        if compression.get('is_suspicious', False):
            score -= compression.get('blockiness_score', 0) * 10 * weights['compression']
            
        # Deductions from ELA
        if ela.get('is_suspicious', False):
            score -= ela.get('suspicion_score', 0) * weights['ela']
            
        return max(0, min(100, score))

    def _collect_tampering_indicators(self, *analyses) -> list:
        """Gathers all human-readable tampering indicators."""
        exif_analysis, copy_move, compression, ela = analyses
        indicators = []
        
        indicators.extend(exif_analysis.get('suspicious_indicators', []))
        
        if copy_move.get('detected', False):
            indicators.append(f"Copy-move forgery detected with {copy_move['confidence']}% confidence.")
            
        if compression.get('is_suspicious', False):
            indicators.append(f"High JPEG blockiness detected (score: {compression['blockiness_score']}), suggesting manipulation.")
            
        if ela.get('is_suspicious', False):
            indicators.append(f"Inconsistent error levels found (ELA score: {ela['suspicion_score']}), suggesting tampered regions.")
            
        return indicators


class MetadataAnalyzer(ForensicAnalyzer):
    """Backward-compatible alias for existing integrations."""
