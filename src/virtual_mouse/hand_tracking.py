"""Hand tracking module using MediaPipe HandLandmarker."""

import cv2
import numpy as np
import mediapipe as mp
import logging
from typing import List, Optional, Tuple, Dict
from virtual_mouse import config

logger = logging.getLogger(__name__)

# Standard 21 Hand Connections
HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (5, 9), (9, 10), (10, 11), (11, 12),
    # Ring
    (9, 13), (13, 14), (14, 15), (15, 16),
    # Pinky
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)
]


class HandTracker:
    """Wrapper around MediaPipe HandLandmarker for real-time 21-landmark tracking."""

    def __init__(self, model_path: str = str(config.MODEL_PATH), max_hands: int = 1):
        self.model_path = model_path
        self.max_hands = max_hands
        self.landmarker = None
        self._init_landmarker()

    def _init_landmarker(self) -> None:
        """Initializes the MediaPipe HandLandmarker."""
        try:
            BaseOptions = mp.tasks.BaseOptions
            HandLandmarker = mp.tasks.vision.HandLandmarker
            HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
            VisionRunningMode = mp.tasks.vision.RunningMode

            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=self.model_path),
                running_mode=VisionRunningMode.IMAGE,
                num_hands=self.max_hands,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.6,
                min_tracking_confidence=0.6
            )
            self.landmarker = HandLandmarker.create_from_options(options)
            logger.info("MediaPipe HandLandmarker initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe HandLandmarker: {e}")
            raise

    def process_frame(self, frame_bgr: np.ndarray) -> Optional[List[Dict[str, int]]]:
        """
        Detects hand landmarks in a BGR frame.
        Returns a list of 21 landmark dictionaries with keys:
          'id', 'x' (pixel), 'y' (pixel), 'z' (normalized depth)
        Returns None if no hand detected.
        """
        if self.landmarker is None:
            return None

        h, w, _ = frame_bgr.shape
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

        result = self.landmarker.detect(mp_image)

        if not result.hand_landmarks:
            return None

        # Take primary detected hand
        raw_landmarks = result.hand_landmarks[0]
        landmarks = []
        for idx, lm in enumerate(raw_landmarks):
            px = int(lm.x * w)
            py = int(lm.y * h)
            landmarks.append({
                "id": idx,
                "x": px,
                "y": py,
                "z": lm.z,
                "x_norm": lm.x,
                "y_norm": lm.y
            })
        return landmarks

    def draw_landmarks(self, frame: np.ndarray, landmarks: List[Dict[str, int]]) -> None:
        """Renders landmark points and skeletal bone connections on the frame."""
        if not landmarks:
            return

        # Draw bone connections
        for start_idx, end_idx in HAND_CONNECTIONS:
            pt1 = (landmarks[start_idx]["x"], landmarks[start_idx]["y"])
            pt2 = (landmarks[end_idx]["x"], landmarks[end_idx]["y"])
            cv2.line(frame, pt1, pt2, (200, 200, 200), 2, cv2.LINE_AA)

        # Draw key joints and fingertips
        for idx, lm in enumerate(landmarks):
            pt = (lm["x"], lm["y"])
            # Fingertips (4, 8, 12, 16, 20) highlighted in vivid accent color
            if idx in (4, 8, 12, 16, 20):
                cv2.circle(frame, pt, 7, config.COLOR_WARNING, -1, cv2.LINE_AA)
                cv2.circle(frame, pt, 9, (255, 255, 255), 1, cv2.LINE_AA)
            else:
                cv2.circle(frame, pt, 4, config.COLOR_PRIMARY, -1, cv2.LINE_AA)

    def close(self) -> None:
        """Closes the landmarker instance."""
        if self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None
