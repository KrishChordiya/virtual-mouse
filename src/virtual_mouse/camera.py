"""Camera management module for webcam capture and frame preprocessing."""

import cv2
import logging
from typing import Optional, Tuple
from virtual_mouse import config

logger = logging.getLogger(__name__)


class Camera:
    """Manages OpenCV webcam initialization, frame capture, and cleanup."""

    def __init__(self, camera_index: int = config.CAMERA_INDEX,
                 width: int = config.FRAME_WIDTH,
                 height: int = config.FRAME_HEIGHT):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.cap: Optional[cv2.VideoCapture] = None

    def start(self) -> bool:
        """Initializes the webcam device."""
        logger.info(f"Connecting to camera index {self.camera_index}...")
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            logger.error(f"Failed to open camera index {self.camera_index}")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)
        logger.info("Camera initialized successfully.")
        return True

    def read_frame(self) -> Tuple[bool, Optional[cv2.Mat]]:
        """Captures a single frame, applies horizontal mirroring, and returns it."""
        if self.cap is None or not self.cap.isOpened():
            return False, None

        ret, frame = self.cap.read()
        if not ret or frame is None:
            return False, None

        # Horizontal flip (mirror mode) for intuitive gesture control
        frame = cv2.flip(frame, 1)
        return True, frame

    def release(self) -> None:
        """Releases the camera device safely."""
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            logger.info("Camera released.")
        self.cap = None
