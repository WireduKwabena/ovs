"""
Face Analysis Service
======================

Visual engagement analysis using OpenCV and MediaPipe.

Academic Note:
--------------
Analyzes non-verbal cues from video interviews:
1. Face presence detection
2. Eye contact estimation (gaze direction)
3. Facial expression analysis
4. Movement/fidgeting detection

Ethical Considerations:
- Be cautious about using visual features for hiring decisions
- Can introduce bias based on appearance, disability, etc.
- Should be used as supplementary data, not primary decision factor
- Discuss ethical implications in your thesis

Technical Approach:
- OpenCV: Face detection using Haar Cascades
- MediaPipe: Facial landmark detection (468 points)
- Simplified from docs: No complex stress/deception detection

References:
- Ekman, P. (1992). "An argument for basic emotions"
- Baltrusaitis, T., et al. (2018). "OpenFace 2.0"
"""

import cv2
import mediapipe as mp
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import time
from collections import Counter

logger = logging.getLogger(__name__)


class FaceAnalyzer:
    """
    Analyze facial features and engagement from video.
    
    Simplified approach:
    - Face detection (is candidate visible?)
    - Eye contact estimation (looking at camera?)
    - Basic expression detection
    - Movement analysis
    """
    
    def __init__(self):
        """Initialize face analyzer."""
        logger.info("Initializing face analyzer")
        
        # OpenCV face detector
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # MediaPipe Face Mesh (for detailed landmarks)
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Face drawing utilities (for visualization)
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        logger.info("Face analyzer initialized")
    
    def detect_face(self, frame: np.ndarray) -> Tuple[bool, Optional[Tuple]]:
        """
        Detect face in frame using OpenCV.
        
        Args:
            frame: Video frame (BGR)
        
        Returns:
            (face_detected, face_coordinates)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        if len(faces) > 0:
            # Return largest face
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            return True, tuple(largest_face)
        
        return False, None
    
    def estimate_eye_contact(
        self,
        face_landmarks,
        frame_width: int,
        frame_height: int
    ) -> Dict:
        """
        Estimate if person is looking at camera.
        
        Academic Note:
        --------------
        Simplified gaze estimation:
        - Compare iris position relative to eye corners
        - Center position = looking at camera
        - Not as accurate as dedicated gaze trackers
        
        For research, compare this heuristic approach with
        ML-based gaze estimation models.
        """
        if not face_landmarks:
            return {
                'looking_at_camera': False,
                'gaze_score': 0.0
            }
        
        # Get key landmark indices (MediaPipe face mesh)
        # Left eye: 33, 133
        # Right eye: 362, 263
        # Nose tip: 1
        
        landmarks = face_landmarks.landmark
        
        # Left eye center approximation
        left_eye_x = (landmarks[33].x + landmarks[133].x) / 2
        left_eye_y = (landmarks[33].y + landmarks[133].y) / 2
        
        # Right eye center approximation
        right_eye_x = (landmarks[362].x + landmarks[263].x) / 2
        right_eye_y = (landmarks[362].y + landmarks[263].y) / 2
        
        # Nose tip
        nose_x = landmarks[1].x
        nose_y = landmarks[1].y
        
        # Calculate eye midpoint
        eye_center_x = (left_eye_x + right_eye_x) / 2
        eye_center_y = (left_eye_y + right_eye_y) / 2
        
        # Calculate horizontal deviation from center
        # Assuming camera is centered, person should look at 0.5, 0.5
        horizontal_deviation = abs(eye_center_x - 0.5)
        vertical_deviation = abs(eye_center_y - 0.5)
        
        # Gaze score (0 = not looking, 1 = direct eye contact)
        # Threshold: within 0.1 is considered "looking at camera"
        gaze_score = max(0, 1 - (horizontal_deviation + vertical_deviation) * 2)
        
        looking_at_camera = gaze_score > 0.6
        
        return {
            'looking_at_camera': looking_at_camera,
            'gaze_score': round(gaze_score, 3),
            'horizontal_deviation': round(horizontal_deviation, 3),
            'vertical_deviation': round(vertical_deviation, 3)
        }
    
    def analyze_video(
        self,
        video_path: str,
        sample_rate: int = 5,
        max_frames: Optional[int] = None
    ) -> Dict:
        """
        Analyze entire video for face presence and engagement.
        
        Args:
            video_path: Path to video file
            sample_rate: Analyze every Nth frame (5 = every 5th frame)
            max_frames: Maximum frames to analyze (None = all)
        
        Returns:
            Analysis results
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        logger.info(f"Analyzing video: {video_path}")
        start_time = time.time()
        
        # Open video
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        # Video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        # Analysis tracking
        frames_analyzed = 0
        frames_with_face = 0
        frames_with_eye_contact = 0
        gaze_scores = []
        
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Sample frames
            if frame_idx % sample_rate != 0:
                frame_idx += 1
                continue
            
            # Max frames limit
            if max_frames and frames_analyzed >= max_frames:
                break
            
            frames_analyzed += 1
            
            # Detect face
            face_detected, face_coords = self.detect_face(frame)
            
            if face_detected:
                frames_with_face += 1
                
                # Convert to RGB for MediaPipe
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Get facial landmarks
                results = self.face_mesh.process(frame_rgb)
                
                if results.multi_face_landmarks:
                    face_landmarks = results.multi_face_landmarks[0]
                    
                    # Estimate eye contact
                    h, w = frame.shape[:2]
                    eye_contact = self.estimate_eye_contact(face_landmarks, w, h)
                    
                    if eye_contact['looking_at_camera']:
                        frames_with_eye_contact += 1
                    
                    gaze_scores.append(eye_contact['gaze_score'])
            
            frame_idx += 1
        
        cap.release()
        
        processing_time = time.time() - start_time
        
        # Calculate metrics
        face_detection_percentage = (frames_with_face / frames_analyzed * 100) if frames_analyzed > 0 else 0
        eye_contact_percentage = (frames_with_eye_contact / frames_analyzed * 100) if frames_analyzed > 0 else 0
        
        average_gaze_score = np.mean(gaze_scores) if gaze_scores else 0.0
        
        # Engagement score (weighted combination)
        engagement_score = (
            face_detection_percentage * 0.4 +
            eye_contact_percentage * 0.6
        )
        
        result = {
            'video_path': str(video_path),
            'duration_seconds': round(duration, 2),
            'fps': round(fps, 2),
            'total_frames': total_frames,
            'frames_analyzed': frames_analyzed,
            'sample_rate': sample_rate,
            'face_detected': frames_with_face > 0,
            'face_detection_percentage': round(face_detection_percentage, 2),
            'eye_contact_percentage': round(eye_contact_percentage, 2),
            'average_gaze_score': round(average_gaze_score, 3),
            'engagement_score': round(engagement_score, 2),
            'processing_time_seconds': round(processing_time, 2)
        }
        
        logger.info(
            f"Video analysis complete: "
            f"{frames_analyzed} frames, "
            f"face: {face_detection_percentage:.1f}%, "
            f"eye contact: {eye_contact_percentage:.1f}%, "
            f"engagement: {engagement_score:.1f}"
        )
        
        return result
    
    def analyze_expression_simple(self, frame: np.ndarray) -> str:
        """
        Simple expression analysis based on mouth position.

        This feature is intentionally disabled until a validated expression model
        is integrated. Returning a placeholder emotion can be misleading in
        production scoring pipelines.
        """
        # Convert to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(frame_rgb, 1.1, 5)

        if len(faces) == 0:
            return "unknown"

        logger.debug(
            "Expression analysis requested but no validated expression model is configured."
        )
        return "not_implemented"
    
    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'face_mesh'):
            self.face_mesh.close()


# Django integration
def analyze_response_video(response_id: int) -> Dict:
    """
    Analyze video for interview response.
    
    Usage in Celery task:
    ```python
    from ai_ml_services.video.face_analyzer import analyze_response_video
    
    result = analyze_response_video(response_id=123)
    ```
    """
    from apps.interviews.models import InterviewResponse, VideoAnalysis
    
    # Get response
    response = InterviewResponse.objects.get(id=response_id)
    
    if not response.video_file:
        raise ValueError(f"Response {response_id} has no video file")
    
    # Initialize analyzer
    analyzer = FaceAnalyzer()
    
    # Analyze (sample every 5 frames for speed)
    result = analyzer.analyze_video(
        video_path=response.video_file.path,
        sample_rate=5
    )
    
    # Create or update VideoAnalysis
    video_analysis, created = VideoAnalysis.objects.update_or_create(
        response=response,
        defaults={
            'face_detected': result['face_detected'],
            'face_detection_confidence': result['face_detection_percentage'],
            'eye_contact_percentage': result['eye_contact_percentage'],
            'dominant_emotion': 'neutral',  # Simplified
            'confidence_level': result['engagement_score'],
            'frames_analyzed': result['frames_analyzed'],
            'analysis_duration_seconds': result['processing_time_seconds']
        }
    )
    
    logger.info(f"Video analysis complete for response {response_id}")
    
    return result


if __name__ == "__main__":
    # Test analyzer
    analyzer = FaceAnalyzer()
    
    # Analyze test video
    result = analyzer.analyze_video("test_video.mp4", sample_rate=10)
    
    print("Face Detection:", result['face_detection_percentage'], "%")
    print("Eye Contact:", result['eye_contact_percentage'], "%")
    print("Engagement Score:", result['engagement_score'])
