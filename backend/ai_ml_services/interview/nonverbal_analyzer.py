"""Non-verbal interview analysis helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict

import cv2

try:
    import mediapipe as mp
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    mp = None

logger = logging.getLogger(__name__)

try:
    from deepface import DeepFace
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    DeepFace = None


class NonVerbalAnalyzer:
    """Real-time non-verbal behavior analysis."""

    def __init__(self):
        self.deepface_available = DeepFace is not None
        self.mediapipe_available = mp is not None and hasattr(mp, "solutions")

        self.face_mesh = None
        self.pose = None

        if self.mediapipe_available:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.mp_pose = mp.solutions.pose
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                max_num_faces=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self.pose = self.mp_pose.Pose(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        else:
            logger.warning(
                "MediaPipe solutions API is unavailable. Non-verbal analysis will use fallback metrics."
            )

    async def analyze_video_async(self, video_path: str) -> Dict:
        """Async wrapper used by websocket handlers."""
        return await asyncio.to_thread(self.analyze_video_stream, video_path)

    def analyze_video_stream(self, video_path: str) -> Dict:
        """Analyze entire video for non-verbal cues."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("Could not open video %s. Returning fallback metrics.", video_path)
            return self._fallback_metrics()

        analysis = {
            "facial_expressions": [],
            "gaze_data": [],
            "head_poses": [],
            "body_movements": [],
            "microexpressions": [],
        }

        frame_count = 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        if fps <= 0:
            fps = 30

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            timestamp = frame_count / fps

            if self.deepface_available:
                try:
                    emotion_result = DeepFace.analyze(
                        frame,
                        actions=["emotion"],
                        enforce_detection=False,
                    )
                    analysis["facial_expressions"].append(
                        {
                            "timestamp": timestamp,
                            "emotion": emotion_result[0]["dominant_emotion"],
                            "scores": emotion_result[0]["emotion"],
                        }
                    )
                except Exception:
                    pass

            if self.mediapipe_available and self.face_mesh is not None and self.pose is not None:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_results = self.face_mesh.process(rgb_frame)

                if face_results.multi_face_landmarks:
                    landmarks = face_results.multi_face_landmarks[0]
                    gaze_data = self._estimate_gaze(landmarks)
                    analysis["gaze_data"].append({"timestamp": timestamp, **gaze_data})

                    head_pose = self._estimate_head_pose(landmarks)
                    analysis["head_poses"].append({"timestamp": timestamp, **head_pose})

                pose_results = self.pose.process(rgb_frame)
                if pose_results.pose_landmarks:
                    body_data = self._analyze_body_language(pose_results.pose_landmarks)
                    analysis["body_movements"].append({"timestamp": timestamp, **body_data})

            frame_count += 1

        cap.release()
        return self._compute_metrics(analysis)

    @staticmethod
    def _estimate_gaze(landmarks) -> Dict:
        left_eye = landmarks.landmark[33]
        right_eye = landmarks.landmark[263]
        eye_y_avg = (left_eye.y + right_eye.y) / 2
        looking_at_camera = 0.4 < eye_y_avg < 0.6
        return {
            "looking_at_camera": looking_at_camera,
            "eye_y_position": eye_y_avg,
        }

    @staticmethod
    def _estimate_head_pose(landmarks) -> Dict:
        nose_tip = landmarks.landmark[1]
        yaw = (nose_tip.x - 0.5) * 90
        pitch = (0.5 - nose_tip.y) * 45
        return {
            "yaw": yaw,
            "pitch": pitch,
            "looking_down": pitch < -15,
            "looking_away": abs(yaw) > 20,
        }

    @staticmethod
    def _analyze_body_language(pose_landmarks) -> Dict:
        left_shoulder = pose_landmarks.landmark[11]
        right_shoulder = pose_landmarks.landmark[12]
        left_wrist = pose_landmarks.landmark[15]
        right_wrist = pose_landmarks.landmark[16]

        face_y = pose_landmarks.landmark[0].y
        hands_near_face = (
            abs(left_wrist.y - face_y) < 0.2 or abs(right_wrist.y - face_y) < 0.2
        )
        shoulder_diff = abs(left_shoulder.y - right_shoulder.y)
        return {
            "hands_near_face": hands_near_face,
            "shoulder_asymmetry": shoulder_diff,
            "posture_stable": shoulder_diff < 0.05,
        }

    def _compute_metrics(self, analysis: Dict) -> Dict:
        gaze_data = analysis["gaze_data"]
        body_movements = analysis["body_movements"]
        expressions = analysis["facial_expressions"]

        looking_at_camera_frames = sum(
            1 for gaze in gaze_data if gaze.get("looking_at_camera")
        )
        eye_contact_pct = (looking_at_camera_frames / len(gaze_data) * 100) if gaze_data else 0

        emotions = [face["emotion"] for face in expressions]
        if emotions:
            most_common_emotion = max(set(emotions), key=emotions.count)
            emotion_consistency = emotions.count(most_common_emotion) / len(emotions) * 100
        else:
            most_common_emotion = "neutral"
            emotion_consistency = 100

        stress_indicators = []

        fidget_frames = sum(1 for movement in body_movements if movement.get("hands_near_face"))
        body_len = len(body_movements)
        if body_len > 0 and (fidget_frames / body_len) > 0.3:
            stress_indicators.append("frequent_fidgeting")

        if eye_contact_pct < 50:
            stress_indicators.append("poor_eye_contact")

        emotion_changes = 0
        for idx in range(1, len(emotions)):
            if emotions[idx] != emotions[idx - 1]:
                emotion_changes += 1
        if emotions and emotion_changes > len(emotions) * 0.3:
            stress_indicators.append("emotional_instability")

        deception_score = 0.0
        deception_score += (100 - eye_contact_pct) * 0.4
        deception_score += (100 - emotion_consistency) * 0.3
        if body_len > 0:
            deception_score += min((fidget_frames / body_len) * 200, 30)

        deception_score = min(max(deception_score, 0), 100)
        confidence_score = 100 - deception_score

        return {
            "eye_contact_percentage": eye_contact_pct,
            "average_emotion": most_common_emotion,
            "emotion_consistency": emotion_consistency,
            "fidgeting_detected": body_len > 0 and fidget_frames > body_len * 0.2,
            "stress_indicators": stress_indicators,
            "deception_score": deception_score,
            "confidence_score": confidence_score,
            "behavioral_red_flags": stress_indicators,
        }

    @staticmethod
    def _fallback_metrics() -> Dict:
        return {
            "eye_contact_percentage": 0,
            "average_emotion": "neutral",
            "emotion_consistency": 100,
            "fidgeting_detected": False,
            "stress_indicators": [],
            "deception_score": 50.0,
            "confidence_score": 50.0,
            "behavioral_red_flags": [],
        }
