"""Mouse and OS input controller module using PyAutoGUI and native Windows APIs."""

import time
import math
import ctypes
import logging
from collections import deque
from typing import Tuple, Optional
import pyautogui

from virtual_mouse import config
from virtual_mouse.gesture_recognition import GestureType

logger = logging.getLogger(__name__)

# Configure PyAutoGUI for maximum real-time responsiveness
pyautogui.PAUSE = 0.0
pyautogui.FAILSAFE = False

# Ensure Windows DPI awareness so coordinates match physical display resolution
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Windows native horizontal mouse wheel event flag
MOUSEEVENTF_HWHEEL = 0x01000


class MouseController:
    """Handles cursor positioning, clicks, dragging, scrolling, and multi-selection."""

    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()
        self.prev_screen_x = self.screen_width // 2
        self.prev_screen_y = self.screen_height // 2

        # State tracking for clicks and double clicks
        self.last_left_click_time = 0.0
        self.last_right_click_time = 0.0
        self.pinch_start_time: Optional[float] = None
        self.pinch_start_frame_pos: Optional[Tuple[int, int]] = None

        # Pre-click snapshot: the screen position captured the moment pinch begins
        self.click_target_pos: Optional[Tuple[int, int]] = None

        # State tracking for drag-and-drop
        self.is_dragging = False
        self.drag_release_counter = 0
        self.last_drag_screen_pos: Optional[Tuple[int, int]] = None
        self.drop_cooldown_until: float = 0.0

        # State tracking for multi-selection
        self.is_multi_select_active = False

        # State tracking for continuous scrolling
        self.scroll_anchor: Optional[Tuple[int, int]] = None
        self.last_scroll_time = 0.0

        # Current action description for HUD
        self.last_action_desc = "Idle"

    def map_to_screen(self, frame_x: int, frame_y: int,
                      smoothing_override: Optional[float] = None) -> Tuple[int, int]:
        """
        Maps camera coordinates to screen coordinates with center-relative sensitivity scaling.
        Guarantees reaching all 4 screen edges and corners without hands leaving the camera box.
        """
        cx = config.FRAME_WIDTH / 2.0
        cy = config.FRAME_HEIGHT / 2.0
        range_x = (config.FRAME_WIDTH / 2.0) - config.FRAME_MARGIN_X
        range_y = (config.FRAME_HEIGHT / 2.0) - config.FRAME_MARGIN_Y

        # Relative displacement from center (-1.0 to +1.0 at margins)
        rel_x = (frame_x - cx) / max(1.0, range_x)
        rel_y = (frame_y - cy) / max(1.0, range_y)

        # Apply sensitivity multiplier so compact hand motion easily reaches edges
        scaled_x = rel_x * config.CURSOR_SENSITIVITY
        scaled_y = rel_y * config.CURSOR_SENSITIVITY

        # Clamp between -1.0 and +1.0
        clamped_x = max(-1.0, min(1.0, scaled_x))
        clamped_y = max(-1.0, min(1.0, scaled_y))

        # Convert to 0.0 - 1.0 normalized screen coordinates
        norm_x = (clamped_x + 1.0) / 2.0
        norm_y = (clamped_y + 1.0) / 2.0

        target_x = int(norm_x * (self.screen_width - 1))
        target_y = int(norm_y * (self.screen_height - 1))

        target_x = max(0, min(self.screen_width - 1, target_x))
        target_y = max(0, min(self.screen_height - 1, target_y))

        alpha = smoothing_override if smoothing_override is not None else config.CURSOR_SMOOTHING
        smooth_x = int(alpha * target_x + (1.0 - alpha) * self.prev_screen_x)
        smooth_y = int(alpha * target_y + (1.0 - alpha) * self.prev_screen_y)

        self.prev_screen_x = smooth_x
        self.prev_screen_y = smooth_y

        return smooth_x, smooth_y

    def move_cursor(self, frame_x: int, frame_y: int, pinch_distance: float = 999.0) -> None:
        """
        Moves cursor smoothly across the desktop.
        Uses soft slowdown when fingers are approaching pinch to reduce drift,
        but never fully freezes the cursor so it remains responsive.
        """
        # Post-drop stabilization: hold position while fingers separate so item isn't dragged away
        if time.time() < self.drop_cooldown_until:
            if self.last_drag_screen_pos:
                try:
                    pyautogui.moveTo(*self.last_drag_screen_pos)
                except Exception:
                    pass
            return

        # Soft slowdown: as fingers approach pinch, increase smoothing to reduce drift
        # but never fully freeze - the cursor keeps tracking, just more sluggishly
        if pinch_distance < config.PINCH_INTENT_DISTANCE:
            # Linearly interpolate smoothing from normal (0.35) down to heavy (0.12)
            # as distance goes from PINCH_INTENT_DISTANCE down to PINCH_THRESHOLD
            t = max(0.0, (pinch_distance - config.PINCH_THRESHOLD) /
                    max(1.0, config.PINCH_INTENT_DISTANCE - config.PINCH_THRESHOLD))
            slow_alpha = 0.10 + t * (config.CURSOR_SMOOTHING - 0.10)
            smooth_x, smooth_y = self.map_to_screen(frame_x, frame_y, smoothing_override=slow_alpha)
        else:
            smooth_x, smooth_y = self.map_to_screen(frame_x, frame_y)

        try:
            pyautogui.moveTo(smooth_x, smooth_y)
            self.last_action_desc = f"Move -> ({smooth_x}, {smooth_y})"
        except Exception as e:
            logger.debug(f"Cursor move error: {e}")

    def handle_pinch_index(self, frame_x: int, frame_y: int) -> str:
        """
        Handles Thumb + Index pinch gesture:
        - On first frame of pinch: snapshot current cursor position as click target.
        - If dragging: moves held item across screen with heavy smoothing.
        - If not dragging: evaluates duration and displacement to initiate drag mode.
        - Stationary pinch: holds cursor at snapshot position for clean click.
        """
        now = time.time()
        self.drag_release_counter = 0

        if self.pinch_start_time is None:
            # FIRST FRAME OF PINCH: snapshot the current cursor position immediately
            self.pinch_start_time = now
            self.pinch_start_frame_pos = (frame_x, frame_y)
            self.click_target_pos = (self.prev_screen_x, self.prev_screen_y)

        if self.is_dragging:
            # During drag: use heavier smoothing to eliminate jiggle
            sx, sy = self.map_to_screen(frame_x, frame_y,
                                        smoothing_override=config.DRAG_SMOOTHING)
            self.last_drag_screen_pos = (sx, sy)
            try:
                pyautogui.moveTo(sx, sy)
                self.last_action_desc = "Dragging File / Folder..."
            except Exception as e:
                logger.debug(f"Drag move error: {e}")
            return self.last_action_desc

        duration = now - self.pinch_start_time
        dist_moved = 0.0
        if self.pinch_start_frame_pos:
            dist_moved = math.hypot(
                frame_x - self.pinch_start_frame_pos[0],
                frame_y - self.pinch_start_frame_pos[1]
            )

        # Transition to drag if held beyond threshold and moved deliberately
        if duration >= config.DRAG_ACTIVATION_TIME and dist_moved >= config.DRAG_START_DISTANCE:
            # Start drag from the click target position (where cursor was when pinch began)
            if self.click_target_pos:
                try:
                    pyautogui.moveTo(*self.click_target_pos)
                except Exception:
                    pass
            try:
                pyautogui.mouseDown(button='left')
                self.is_dragging = True
                sx, sy = self.map_to_screen(frame_x, frame_y,
                                            smoothing_override=config.DRAG_SMOOTHING)
                self.last_drag_screen_pos = (sx, sy)
                self.last_action_desc = "Drag Started (Holding Item)"
                logger.info("Mouse down: Drag started")
            except Exception as e:
                logger.error(f"Drag start error: {e}")
            return self.last_action_desc

        # While holding pinch but not yet dragging: keep cursor locked at click target
        if self.click_target_pos:
            try:
                pyautogui.moveTo(*self.click_target_pos)
            except Exception:
                pass

        return "Pinching (Tap to Click / Move to Drag)"

    def handle_pinch_release(self, force_drop: bool = False, frame_x: int = 0, frame_y: int = 0) -> str:
        """
        Called when pinch ends or opens.
        - While dragging: locks cursor to drop target before releasing mouse button so item drops accurately.
        - If stationary: executes Single Left Click or Double Click at the snapshot position.
        """
        now = time.time()
        action = ""

        if self.is_dragging:
            if not force_drop:
                self.drag_release_counter += 1
                if self.drag_release_counter < config.DRAG_RELEASE_GRACE_FRAMES:
                    # In grace period: track position but don't drop yet
                    if frame_x > 0 and frame_y > 0:
                        sx, sy = self.map_to_screen(frame_x, frame_y,
                                                    smoothing_override=config.DRAG_SMOOTHING)
                        self.last_drag_screen_pos = (sx, sy)
                        try:
                            pyautogui.moveTo(sx, sy)
                        except Exception:
                            pass
                    return "Dragging (Stabilizing...)"

            # Drop stabilization: lock cursor to intended drop location
            if self.last_drag_screen_pos:
                try:
                    pyautogui.moveTo(*self.last_drag_screen_pos)
                except Exception:
                    pass

            # Release left mouse button
            try:
                pyautogui.mouseUp(button='left')
                action = "Drop (Item Released Successfully)"
                logger.info("Mouse up: Drag ended / Item dropped")
            except Exception as e:
                logger.error(f"Drop error: {e}")

            self.is_dragging = False
            self.drag_release_counter = 0
            self.pinch_start_time = None
            self.pinch_start_frame_pos = None
            self.click_target_pos = None
            # Lock cursor at drop point and freeze for 300ms
            if self.last_drag_screen_pos:
                self.prev_screen_x, self.prev_screen_y = self.last_drag_screen_pos
            self.drop_cooldown_until = now + 0.30
            self.last_action_desc = action
            return action

        # If not dragging, evaluate click
        if self.pinch_start_time is not None:
            # Move cursor to click target before clicking
            if self.click_target_pos:
                try:
                    pyautogui.moveTo(*self.click_target_pos)
                except Exception:
                    pass

            duration = now - self.pinch_start_time
            self.pinch_start_time = None
            self.pinch_start_frame_pos = None

            time_since_last_click = now - self.last_left_click_time

            if time_since_last_click < config.DOUBLE_CLICK_WINDOW:
                try:
                    pyautogui.doubleClick()
                    action = "Double Click"
                    logger.info("Executed: Double Click")
                except Exception as e:
                    logger.error(f"Double click error: {e}")
                self.last_left_click_time = 0.0
            elif time_since_last_click >= config.CLICK_COOLDOWN:
                try:
                    pyautogui.click(button='left')
                    action = "Single Left Click"
                    logger.info("Executed: Single Left Click")
                except Exception as e:
                    logger.error(f"Single left click error: {e}")
                self.last_left_click_time = now

        self.click_target_pos = None
        self.last_action_desc = action or self.last_action_desc
        return action

    def handle_right_click(self) -> str:
        """Executes a single right mouse click with cooldown."""
        now = time.time()
        if now - self.last_right_click_time > config.CLICK_COOLDOWN:
            try:
                pyautogui.rightClick()
                self.last_right_click_time = now
                self.last_action_desc = "Single Right Click"
                logger.info("Executed: Single Right Click")
                return self.last_action_desc
            except Exception as e:
                logger.error(f"Right click error: {e}")
        return "Right Click Cooldown"

    def handle_scroll(self, curr_x: int, curr_y: int) -> str:
        """
        Continuous rate-based scrolling (joystick auto-scroll):
        - Anchor point (x0, y0) is captured when entering dual-finger mode.
        - Raising hand above anchor continuously scrolls UP indefinitely.
        - Lowering hand below anchor continuously scrolls DOWN indefinitely.
        - Tilting left/right continuously scrolls horizontally.
        - Speed scales dynamically with distance from anchor.
        - Hand never needs to leave the interaction bounding box.
        """
        now = time.time()

        if self.scroll_anchor is None:
            self.scroll_anchor = (curr_x, curr_y)
            self.last_action_desc = "Scroll Ready (Tilt hand to scroll)"
            return self.last_action_desc

        if now - self.last_scroll_time < config.SCROLL_COOLDOWN:
            return self.last_action_desc

        self.last_scroll_time = now
        anchor_x, anchor_y = self.scroll_anchor

        dy = curr_y - anchor_y
        dx = curr_x - anchor_x

        action = ""
        if abs(dy) >= abs(dx):
            if abs(dy) > config.SCROLL_DEADZONE:
                offset = abs(dy) - config.SCROLL_DEADZONE
                speed = int((offset / 7.0) ** 1.35 * 28.0 * config.SCROLL_SPEED_FACTOR)
                speed = max(20, min(800, speed))

                if dy < 0:
                    pyautogui.scroll(speed)
                    action = f"▲ Continuous Scroll UP (Speed: {speed})"
                else:
                    pyautogui.scroll(-speed)
                    action = f"▼ Continuous Scroll DOWN (Speed: {speed})"
            else:
                action = "Scroll Paused (Centered in Deadzone)"
        else:
            if abs(dx) > config.SCROLL_DEADZONE:
                h_offset = abs(dx) - config.SCROLL_DEADZONE
                h_speed = int((h_offset / 7.0) ** 1.35 * 35.0)
                h_speed = max(30, min(1000, h_speed))
                wheel_delta = h_speed if dx > 0 else -h_speed

                try:
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, wheel_delta, 0)
                    dir_str = "► RIGHT" if dx > 0 else "◄ LEFT"
                    action = f"Continuous Scroll {dir_str} (Speed: {h_speed})"
                except Exception as e:
                    logger.debug(f"Horizontal scroll error: {e}")
            else:
                action = "Scroll Paused (Centered in Deadzone)"

        self.last_action_desc = action or self.last_action_desc
        return self.last_action_desc

    def reset_scroll_anchor(self) -> None:
        """Resets the reference anchor point when exiting scroll mode."""
        self.scroll_anchor = None

    def set_multi_select(self, active: bool, frame_x: int, frame_y: int) -> str:
        """
        Handles multiple selection:
        Toggles or holds Ctrl key down and allows marquee selection or multi-item clicking.
        """
        if active and not self.is_multi_select_active:
            try:
                pyautogui.keyDown('ctrl')
                self.is_multi_select_active = True
                self.last_action_desc = "Multi-Select (Ctrl Held)"
                logger.info("Multi-select active: Ctrl key pressed down")
            except Exception as e:
                logger.error(f"Error holding Ctrl: {e}")
        elif not active and self.is_multi_select_active:
            try:
                pyautogui.keyUp('ctrl')
                self.is_multi_select_active = False
                self.last_action_desc = "Multi-Select Released"
                logger.info("Multi-select inactive: Ctrl key released")
            except Exception as e:
                logger.error(f"Error releasing Ctrl: {e}")

        if active:
            self.move_cursor(frame_x, frame_y)

        return self.last_action_desc

    def reset_all_states(self) -> None:
        """
        Failsafe reset triggered by Neutral gesture or application exit.
        Safely releases mouse buttons and modifier keys.
        """
        if self.is_dragging:
            try:
                pyautogui.mouseUp(button='left')
                logger.info("Neutral reset: Released left mouse button")
            except Exception:
                pass
            self.is_dragging = False
            self.drag_release_counter = 0

        if self.is_multi_select_active:
            try:
                pyautogui.keyUp('ctrl')
                logger.info("Neutral reset: Released Ctrl key")
            except Exception:
                pass
            self.is_multi_select_active = False

        self.pinch_start_time = None
        self.pinch_start_frame_pos = None
        self.click_target_pos = None
        self.last_drag_screen_pos = None
        self.drop_cooldown_until = 0.0
        self.scroll_anchor = None
        self.last_action_desc = "Neutral / Idle (All Released)"
