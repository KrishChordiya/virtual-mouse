"""Main application coordinator and HUD renderer for Gesture-Controlled Virtual Mouse."""

import cv2
import time
import logging
import sys
from typing import Optional, Dict, Tuple

from virtual_mouse import config
from virtual_mouse.camera import Camera
from virtual_mouse.hand_tracking import HandTracker
from virtual_mouse.gesture_recognition import GestureRecognizer, GestureType
from virtual_mouse.mouse_controller import MouseController
from virtual_mouse.system_controls import SystemController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("virtual_mouse")


class VirtualMouseApp:
    """Coordinates camera capture, hand tracking, gesture dispatch, and HUD display."""

    def __init__(self):
        self.camera = Camera()
        self.tracker: Optional[HandTracker] = None
        self.recognizer = GestureRecognizer()
        self.mouse = MouseController()
        self.system = SystemController()

        # State tracking
        self.was_pinching_index = False
        self.prev_time = time.time()
        self.fps = 0.0

    def start(self) -> None:
        """Initializes components and runs the main processing loop."""
        logger.info("Starting Gesture-Controlled Virtual Mouse...")

        if not self.camera.start():
            logger.error("Could not start camera. Exiting.")
            sys.exit(1)

        try:
            self.tracker = HandTracker()
        except Exception as e:
            logger.error(f"Failed to initialize HandTracker: {e}")
            self.camera.release()
            sys.exit(1)

        cv2.namedWindow("Gesture-Controlled Virtual Mouse", cv2.WINDOW_AUTOSIZE)

        try:
            self._main_loop()
        finally:
            self._cleanup()

    def _main_loop(self) -> None:
        """Processes video frames continuously until user quits."""
        while True:
            success, frame = self.camera.read_frame()
            if not success or frame is None:
                logger.warning("Frame acquisition dropped. Retrying...")
                time.sleep(0.01)
                continue

            curr_time = time.time()
            dt = curr_time - self.prev_time
            self.prev_time = curr_time
            if dt > 0:
                self.fps = (0.9 * self.fps) + (0.1 * (1.0 / dt))

            landmarks = self.tracker.process_frame(frame)

            gesture_label = "No Hand Detected"
            action_label = self.mouse.last_action_desc
            slider_info = None
            active_reticle = None  # (anchor_pos, current_pos, mode_name, deadzone)

            if landmarks:
                self.tracker.draw_landmarks(frame, landmarks)

                gesture, info = self.recognizer.classify_gesture(
                    landmarks, is_currently_dragging=self.mouse.is_dragging
                )
                gesture_label = gesture.name
                ix, iy = info.get("index_pos", (0, 0))
                hx, hy = info.get("hand_center_pos", (ix, iy))

                if gesture == GestureType.NEUTRAL:
                    self.mouse.reset_all_states()
                    self.system.reset_volume_anchor()
                    self.system.reset_brightness_anchor()
                    self.was_pinching_index = False
                    action_label = "Neutral: Operations Cleared / Dropped"

                elif gesture == GestureType.MOVE:
                    pinch_intent = info.get("pinch_intent", False)
                    self.mouse.move_cursor(ix, iy, is_pinch_intent=pinch_intent)
                    action_label = self.mouse.last_action_desc

                elif gesture == GestureType.PINCH_INDEX:
                    self.was_pinching_index = True
                    action_label = self.mouse.handle_pinch_index(ix, iy)

                elif gesture == GestureType.PINCH_MIDDLE:
                    # Single Right Click
                    action_label = self.mouse.handle_right_click()

                elif gesture == GestureType.SCROLL_DUAL:
                    action_label = self.mouse.handle_scroll(ix, iy)
                    if self.mouse.scroll_anchor:
                        active_reticle = (
                            self.mouse.scroll_anchor,
                            (ix, iy),
                            "Scroll",
                            config.SCROLL_DEADZONE,
                            "Tilt UP/DOWN to scroll continuously"
                        )

                elif gesture == GestureType.MULTI_SELECT:
                    action_label = self.mouse.set_multi_select(True, ix, iy)

                elif gesture == GestureType.VOLUME_CONTROL:
                    # Continuous Rate-Based Volume Joystick
                    vol, v_desc = self.system.adjust_volume_continuous(hx, hy)
                    action_label = v_desc
                    slider_info = ("VOLUME", int(vol), config.COLOR_SUCCESS)
                    if self.system.volume_anchor:
                        active_reticle = (
                            self.system.volume_anchor,
                            (hx, hy),
                            "Volume",
                            config.CONTROL_DEADZONE,
                            "Tilt UP for Volume UP / DOWN for Volume DOWN"
                        )

                elif gesture == GestureType.BRIGHTNESS_CONTROL:
                    # Continuous Rate-Based Brightness Joystick
                    bri, b_desc = self.system.adjust_brightness_continuous(hx, hy)
                    action_label = b_desc
                    slider_info = ("BRIGHTNESS", bri, config.COLOR_WARNING)
                    if self.system.brightness_anchor:
                        active_reticle = (
                            self.system.brightness_anchor,
                            (hx, hy),
                            "Brightness",
                            config.CONTROL_DEADZONE,
                            "Tilt UP for Brightness UP / DOWN for Brightness DOWN"
                        )

                # Release handlers when exiting specific gestures
                if gesture != GestureType.PINCH_INDEX and self.was_pinching_index:
                    force_drop = (gesture == GestureType.NEUTRAL)
                    release_action = self.mouse.handle_pinch_release(
                        force_drop=force_drop, frame_x=ix, frame_y=iy
                    )
                    if release_action:
                        action_label = release_action
                    if not self.mouse.is_dragging:
                        self.was_pinching_index = False

                if gesture != GestureType.SCROLL_DUAL:
                    self.mouse.reset_scroll_anchor()

                if gesture != GestureType.VOLUME_CONTROL:
                    self.system.reset_volume_anchor()

                if gesture != GestureType.BRIGHTNESS_CONTROL:
                    self.system.reset_brightness_anchor()

                if gesture != GestureType.MULTI_SELECT and self.mouse.is_multi_select_active:
                    self.mouse.set_multi_select(False, 0, 0)

            else:
                # Hand lost
                if self.mouse.is_dragging:
                    self.mouse.drag_release_counter += 1
                    if self.mouse.drag_release_counter >= config.DRAG_RELEASE_GRACE_FRAMES:
                        self.mouse.reset_all_states()
                        self.was_pinching_index = False
                else:
                    self.mouse.reset_all_states()
                    self.was_pinching_index = False

                self.system.reset_volume_anchor()
                self.system.reset_brightness_anchor()

            # Draw HUD Overlays
            self._draw_hud(frame, gesture_label, action_label, slider_info, active_reticle)

            # Display feed
            cv2.imshow("Gesture-Controlled Virtual Mouse", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                logger.info("Exit key pressed by user.")
                break

    def _draw_hud(self, frame: cv2.Mat, gesture_name: str, action_desc: str,
                  slider_info: Optional[tuple], active_reticle: Optional[tuple] = None) -> None:
        """Renders heads-up display information, reticle, and visual guides on the camera frame."""
        h, w, _ = frame.shape

        # 1. Interaction Zone Box
        x1, x2 = config.FRAME_MARGIN_X, w - config.FRAME_MARGIN_X
        y1, y2 = config.FRAME_MARGIN_Y, h - config.FRAME_MARGIN_Y
        cv2.rectangle(frame, (x1, y1), (x2, y2), (70, 70, 70), 1, cv2.LINE_AA)

        # 2. Header Status Card (Semi-transparent background panel)
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (w - 10, 75), config.COLOR_BG_DARK, -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # FPS Indicator
        cv2.putText(frame, f"FPS: {int(self.fps)}", (w - 110, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, config.COLOR_WARNING, 2, cv2.LINE_AA)

        # Active Gesture Badge
        cv2.putText(frame, f"Gesture: {gesture_name}", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, config.COLOR_PRIMARY, 2, cv2.LINE_AA)

        # Active OS Action Description
        cv2.putText(frame, f"Action: {action_desc}", (20, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, config.COLOR_TEXT, 1, cv2.LINE_AA)

        # 3. Continuous Rate Reticle (Scroll, Volume, or Brightness Joystick)
        if active_reticle is not None:
            anchor_pos, curr_pos, mode_name, deadzone, prompt_text = active_reticle
            ax, ay = anchor_pos
            cx, cy = curr_pos

            # Draw deadzone circle around anchor
            cv2.circle(frame, (ax, ay), deadzone, (100, 100, 100), 1, cv2.LINE_AA)
            cv2.circle(frame, (ax, ay), 3, (0, 255, 255), -1, cv2.LINE_AA)

            # Draw vector line to current position
            cv2.line(frame, (ax, ay), (cx, cy), (0, 215, 255), 2, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), 5, (0, 215, 255), -1, cv2.LINE_AA)

            # Guide text prompt
            cv2.putText(frame, prompt_text, (w // 2 - 190, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1, cv2.LINE_AA)

        # 4. Drag-and-Drop Active Banner
        if self.mouse.is_dragging:
            cv2.rectangle(frame, (10, h - 45), (w - 10, h - 12), (0, 140, 255), -1)
            cv2.putText(frame, "HOLDING ITEM - MOVE ANYWHERE, OPEN PALM TO DROP",
                        (25, h - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)

        # 5. Dynamic Progress Slider for Volume or Brightness
        if slider_info:
            label, percent, color = slider_info
            bar_x = w - 50
            bar_y_top = 100
            bar_y_bottom = h - 60
            bar_h = bar_y_bottom - bar_y_top

            cv2.rectangle(frame, (bar_x, bar_y_top), (bar_x + 25, bar_y_bottom), (50, 50, 50), -1)
            fill_h = int((percent / 100.0) * bar_h)
            cv2.rectangle(frame, (bar_x, bar_y_bottom - fill_h), (bar_x + 25, bar_y_bottom), color, -1)
            cv2.rectangle(frame, (bar_x, bar_y_top), (bar_x + 25, bar_y_bottom), (200, 200, 200), 2)

            cv2.putText(frame, f"{percent}%", (bar_x - 15, bar_y_bottom + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
            cv2.putText(frame, label, (bar_x - 30, bar_y_top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # 6. Footer controls reminder
        if active_reticle is None and not self.mouse.is_dragging:
            cv2.putText(frame, "Press 'Q' or 'Esc' to Exit", (20, h - 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1, cv2.LINE_AA)

    def _cleanup(self) -> None:
        """Safely cleans up resources and releases any active OS holds."""
        logger.info("Executing safe application cleanup...")
        self.mouse.reset_all_states()
        self.system.reset_volume_anchor()
        self.system.reset_brightness_anchor()

        if self.tracker:
            self.tracker.close()
        if self.camera:
            self.camera.release()

        cv2.destroyAllWindows()
        logger.info("Application exited cleanly.")


def main():
    """Application entrypoint."""
    app = VirtualMouseApp()
    app.start()


if __name__ == "__main__":
    main()
