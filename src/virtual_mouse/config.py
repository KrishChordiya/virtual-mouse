"""Centralized configuration for Gesture-Controlled Virtual Mouse."""

import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = PROJECT_ROOT / "assets" / "models" / "hand_landmarker.task"

# Camera Configuration
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 30

# Cursor & Interaction Margins (Webcam frame sub-box mapped to full screen)
# Margins define central active zone; high sensitivity allows reaching all 4 screen edges effortlessly
FRAME_MARGIN_X = 140
FRAME_MARGIN_Y = 110
CURSOR_SENSITIVITY = 1.35     # Multiplier to reach screen edges with compact hand motion

# Mouse Movement Smoothing
# EMA factor: new_pos = SMOOTHING_FACTOR * raw_pos + (1 - SMOOTHING_FACTOR) * prev_pos
CURSOR_SMOOTHING = 0.35
DRAG_SMOOTHING = 0.18         # Heavier smoothing during drag to prevent jiggle

# Gesture Distance Thresholds (in pixel coordinates on 640x480 frame)
PINCH_THRESHOLD = 36          # Thumb to Index distance to register left click/drag
PINCH_MIDDLE_THRESHOLD = 45   # Thumb to Middle distance to register right click
PINCH_MIDDLE_INTENT = 65      # Thumb approaching middle - suppress scroll to allow right click
PINCH_MAINTAIN_THRESHOLD = 52 # Relaxed distance to maintain drag while hand moves
PINCH_INTENT_DISTANCE = 48    # Distance below which cursor starts slowing (soft freeze)
FINGER_CLOSE_THRESHOLD = 40   # Distance to consider two fingertips together

# Timing & Cooldowns (in seconds)
CLICK_COOLDOWN = 0.25         # Minimum delay between successive single clicks
DOUBLE_CLICK_WINDOW = 0.55    # Time window between taps for a double click
DRAG_ACTIVATION_TIME = 0.40   # Pinch hold duration to start drag mode (raised to avoid accidental drag)
DRAG_START_DISTANCE = 20      # Pixel displacement required to trigger drag mode
DRAG_RELEASE_GRACE_FRAMES = 6 # Frame tolerance buffer before dropping item

# Continuous Scrolling Parameters
SCROLL_DEADZONE = 18          # Neutral zone around initial anchor point
SCROLL_SPEED_FACTOR = 0.8     # Multiplier for continuous velocity-based scrolling
SCROLL_COOLDOWN = 0.03        # Frame interval between continuous scroll dispatches

# System Control Parameters (Continuous Joystick Adjustment)
CONTROL_UPDATE_INTERVAL = 0.03  # Interval for volume/brightness updates
CONTROL_DEADZONE = 18           # Deadzone for continuous volume/brightness tilt
CONTROL_SPEED_FACTOR = 1.0      # Speed multiplier for volume/brightness adjustment
VOLUME_SMOOTHING = 0.25
BRIGHTNESS_SMOOTHING = 0.25

# Color Palette for Visual HUD (BGR format for OpenCV)
COLOR_PRIMARY = (255, 140, 0)     # Neon Deep Sky Blue / Orange
COLOR_SUCCESS = (50, 205, 50)     # Lime Green
COLOR_WARNING = (0, 215, 255)     # Gold / Yellow
COLOR_DANGER = (71, 99, 255)      # Coral / Red
COLOR_TEXT = (255, 255, 255)       # White
COLOR_BG_DARK = (25, 25, 25)      # Charcoal
