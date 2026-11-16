"""Gesture recognition and classification module."""

import math
from enum import Enum, auto
from typing import List, Dict, Tuple, Optional
from virtual_mouse import config


class GestureType(Enum):
    """Enumeration of recognized hand gestures."""
    NONE = auto()
    NEUTRAL = auto()              # Open hand (5 fingers) - Reset / Idle / Force Drop
    MOVE = auto()                 # Index finger up only - Cursor navigation
    PINCH_INDEX = auto()          # Thumb + Index pinch - Left Click / Drag
    PINCH_MIDDLE = auto()         # Thumb + Middle pinch - Right Click
    SCROLL_DUAL = auto()          # Index + Middle extended - Continuous Scroll V/H
    MULTI_SELECT = auto()         # Horns: Index + Pinky - Multi-select
    VOLUME_CONTROL = auto()       # Shaka: Thumb + Pinky - Continuous Volume Joystick
    BRIGHTNESS_CONTROL = auto()   # Three fingers: Index + Middle + Ring - Continuous Brightness Joystick


class GestureRecognizer:
    """Classifies 21 hand landmarks into distinct, conflict-free gestures."""

    def __init__(self):
        self.prev_scroll_ref: Optional[Tuple[int, int]] = None

    @staticmethod
    def get_distance(pt1: Dict[str, int], pt2: Dict[str, int]) -> float:
        """Calculates Euclidean distance between two 2D points."""
        return math.hypot(pt1["x"] - pt2["x"], pt1["y"] - pt2["y"])

    def evaluate_fingers(self, landmarks: List[Dict[str, int]]) -> Dict[str, bool]:
        """
        Determines whether each of the 5 fingers is extended.
        Returns a dict: {'thumb': bool, 'index': bool, 'middle': bool, 'ring': bool, 'pinky': bool}
        """
        index_up = landmarks[8]["y"] < landmarks[6]["y"]
        middle_up = landmarks[12]["y"] < landmarks[10]["y"]
        ring_up = landmarks[16]["y"] < landmarks[14]["y"]
        pinky_up = landmarks[20]["y"] < landmarks[18]["y"]

        d_tip = self.get_distance(landmarks[4], landmarks[9])
        d_ip = self.get_distance(landmarks[3], landmarks[9])
        thumb_up = d_tip > (d_ip * 1.15)

        return {
            "thumb": thumb_up,
            "index": index_up,
            "middle": middle_up,
            "ring": ring_up,
            "pinky": pinky_up
        }

    def classify_gesture(self, landmarks: List[Dict[str, int]],
                         is_currently_dragging: bool = False) -> Tuple[GestureType, Dict]:
        """
        Classifies the hand pose into a GestureType and returns auxiliary info.
        """
        if not landmarks or len(landmarks) < 21:
            return GestureType.NONE, {}

        fingers = self.evaluate_fingers(landmarks)
        up_count = sum(1 for v in fingers.values() if v)

        # Compute key pairwise distances
        d_thumb_index = self.get_distance(landmarks[4], landmarks[8])
        d_thumb_middle = self.get_distance(landmarks[4], landmarks[12])
        d_index_middle = self.get_distance(landmarks[8], landmarks[12])
        d_middle_to_mcp = self.get_distance(landmarks[12], landmarks[9])

        # Pinch intent: thumb and index are closing in
        pinch_intent = d_thumb_index < config.PINCH_INTENT_DISTANCE

        info = {
            "fingers": fingers,
            "up_count": up_count,
            "d_thumb_index": d_thumb_index,
            "d_thumb_middle": d_thumb_middle,
            "d_index_middle": d_index_middle,
            "d_middle_to_mcp": d_middle_to_mcp,
            "pinch_intent": pinch_intent,
            "index_pos": (landmarks[8]["x"], landmarks[8]["y"]),
            "wrist_pos": (landmarks[0]["x"], landmarks[0]["y"]),
            "hand_center_pos": (landmarks[9]["x"], landmarks[9]["y"]),
            "hand_center_y": landmarks[9]["y"]
        }

        # 1. Neutral / Open Hand: All 5 fingers extended
        if fingers["thumb"] and fingers["index"] and fingers["middle"] and fingers["ring"] and fingers["pinky"]:
            if d_thumb_index > config.PINCH_THRESHOLD and d_thumb_middle > config.PINCH_MIDDLE_THRESHOLD:
                return GestureType.NEUTRAL, info

        # 2. Pinch Thumb + Index (Left Click / Drag):
        effective_pinch_threshold = config.PINCH_MAINTAIN_THRESHOLD if is_currently_dragging else config.PINCH_THRESHOLD
        if d_thumb_index < effective_pinch_threshold and not fingers["ring"] and not fingers["pinky"]:
            return GestureType.PINCH_INDEX, info

        # 3. Pinch Thumb + Middle (Right Click):
        # Triggered when Thumb and Middle tips touch, regardless of whether Index is raised or folded
        # Must have Ring and Pinky folded, and Thumb NOT touching Index
        if d_thumb_middle < config.PINCH_MIDDLE_THRESHOLD and d_thumb_index > 36 and not fingers["ring"] and not fingers["pinky"]:
            return GestureType.PINCH_MIDDLE, info

        # 4. Multi-Select (Horns): Index UP + Pinky UP, Middle & Ring DOWN
        if fingers["index"] and fingers["pinky"] and not fingers["middle"] and not fingers["ring"]:
            return GestureType.MULTI_SELECT, info

        # 5. Volume Control (Shaka): Thumb UP + Pinky UP, Index & Middle & Ring DOWN
        if fingers["thumb"] and fingers["pinky"] and not fingers["index"] and not fingers["middle"] and not fingers["ring"]:
            return GestureType.VOLUME_CONTROL, info

        # 6. Brightness Control: 3 fingers UP (Index + Middle + Ring UP, Pinky DOWN)
        if fingers["index"] and fingers["middle"] and fingers["ring"] and not fingers["pinky"]:
            return GestureType.BRIGHTNESS_CONTROL, info

        # 7. Scroll Mode: Dual fingers UP (Index + Middle UP, Ring DOWN, Pinky DOWN, separated)
        # CRITICAL GUARD: Must NOT be pinching Thumb to Middle (which is Right Click)
        # CRITICAL GUARD 2: Must NOT have thumb approaching middle (right click intent)
        if fingers["index"] and fingers["middle"] and not fingers["ring"] and not fingers["pinky"]:
            if d_thumb_middle >= config.PINCH_MIDDLE_INTENT and d_thumb_index >= config.PINCH_THRESHOLD:
                if d_index_middle > config.FINGER_CLOSE_THRESHOLD:
                    return GestureType.SCROLL_DUAL, info

        # 8. Cursor Move: Index UP only, other fingers folded
        if fingers["index"] and not fingers["middle"] and not fingers["ring"] and not fingers["pinky"]:
            return GestureType.MOVE, info

        return GestureType.NONE, info
