"""Lightweight non-verbal analysis utilities."""

from __future__ import annotations

from typing import Dict

import cv2
import numpy as np
try:
    import mediapipe as mp
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    mp = None


def analyze_frame(frame: np.ndarray) -> Dict[str, float | str]:
    """Analyze a single frame with simple, dependency-safe heuristics."""
    if frame is None:
        return {"emotion": "unknown", "pose": 0.0}

    if mp is None or not hasattr(mp, "solutions"):
        return {"emotion": "neutral", "pose": 50.0}

    holistic = mp.solutions.holistic.Holistic(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = holistic.process(rgb_frame)
    holistic.close()

    emotion = "neutral"
    pose_score = 50.0

    if results.face_landmarks:
        # Placeholder heuristic: if face is detected, return "engaged".
        emotion = "engaged"

    if results.pose_landmarks:
        left = results.pose_landmarks.landmark[11].y
        right = results.pose_landmarks.landmark[12].y
        shoulder_delta = abs(left - right)
        pose_score = max(0.0, min(100.0, 100.0 - shoulder_delta * 500))

    return {"emotion": emotion, "pose": round(pose_score, 2)}


def deception_score(cv_analysis: Dict[str, float], nlp_sentiment: float) -> float:
    """Compute a bounded deception score without external model loading."""
    pose = float(cv_analysis.get("pose", 50.0))
    # Higher sentiment generally lowers deception risk.
    score = (100.0 - pose) * 0.6 + (1.0 - max(min(nlp_sentiment, 1.0), -1.0)) * 20.0
    return round(max(0.0, min(score, 100.0)), 2)
