"""System volume and screen brightness control module for Windows."""

import time
import logging
from typing import Optional, Tuple
from virtual_mouse import config

logger = logging.getLogger(__name__)

# Try importing pycaw for Windows Audio
try:
    from pycaw.pycaw import AudioUtilities
    PYCAW_AVAILABLE = True
except Exception as e:
    logger.warning(f"Pycaw not available: {e}")
    PYCAW_AVAILABLE = False

# Try importing screen_brightness_control
try:
    import screen_brightness_control as sbc
    SBC_AVAILABLE = True
except Exception as e:
    logger.warning(f"Screen brightness control not available: {e}")
    SBC_AVAILABLE = False


class SystemController:
    """Manages audio volume and monitor brightness adjustments using anchor-based continuous rate control."""

    def __init__(self):
        self.endpoint_volume = None
        self.current_volume_percent: float = 50.0
        self.current_brightness_percent: int = 50

        # Anchor points for continuous joystick adjustments
        self.volume_anchor: Optional[Tuple[int, int]] = None
        self.brightness_anchor: Optional[Tuple[int, int]] = None
        self.last_update_time: float = 0.0

        self._init_volume()
        self._init_brightness()

    def _init_volume(self) -> None:
        """Initializes the Windows default playback endpoint volume interface."""
        if not PYCAW_AVAILABLE:
            return
        try:
            device = AudioUtilities.GetSpeakers()
            if hasattr(device, 'EndpointVolume'):
                self.endpoint_volume = device.EndpointVolume
            elif hasattr(device, 'Activate'):
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import IAudioEndpointVolume
                import ctypes
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.endpoint_volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))

            if self.endpoint_volume:
                scalar = self.endpoint_volume.GetMasterVolumeLevelScalar()
                self.current_volume_percent = float(scalar * 100.0)
                logger.info(f"System volume initialized: {self.current_volume_percent:.1f}%")
        except Exception as e:
            logger.error(f"Error initializing system volume: {e}")
            self.endpoint_volume = None

    def _init_brightness(self) -> None:
        """Initializes display brightness settings."""
        if not SBC_AVAILABLE:
            return
        try:
            b_list = sbc.get_brightness()
            if isinstance(b_list, list) and len(b_list) > 0:
                self.current_brightness_percent = int(b_list[0])
            elif isinstance(b_list, (int, float)):
                self.current_brightness_percent = int(b_list)
            logger.info(f"Screen brightness initialized: {self.current_brightness_percent}%")
        except Exception as e:
            logger.warning(f"Error initializing screen brightness: {e}")

    def adjust_volume_continuous(self, curr_x: int, curr_y: int) -> Tuple[float, str]:
        """
        Rate-based continuous volume adjustment (joystick style):
        - Captures initial hand position as anchor.
        - Tilting UP increases volume continuously at rate proportional to displacement.
        - Tilting DOWN decreases volume continuously at rate proportional to displacement.
        - Hand in center deadzone locks current volume setting.
        """
        now = time.time()

        if self.volume_anchor is None:
            self.volume_anchor = (curr_x, curr_y)
            return self.current_volume_percent, f"Volume Ready: {int(self.current_volume_percent)}%"

        if now - self.last_update_time < config.CONTROL_UPDATE_INTERVAL:
            return self.current_volume_percent, f"Volume: {int(self.current_volume_percent)}%"

        self.last_update_time = now
        _, anchor_y = self.volume_anchor
        dy = curr_y - anchor_y

        action_desc = f"Volume: {int(self.current_volume_percent)}%"

        if abs(dy) > config.CONTROL_DEADZONE:
            offset = abs(dy) - config.CONTROL_DEADZONE
            step = (offset / 8.0) * 1.5 * config.CONTROL_SPEED_FACTOR

            if dy < 0:
                # Hand UP -> Volume UP
                self.current_volume_percent = min(100.0, self.current_volume_percent + step)
                action_desc = f"▲ Volume UP: {int(self.current_volume_percent)}%"
            else:
                # Hand DOWN -> Volume DOWN
                self.current_volume_percent = max(0.0, self.current_volume_percent - step)
                action_desc = f"▼ Volume DOWN: {int(self.current_volume_percent)}%"

            if self.endpoint_volume:
                try:
                    scalar = self.current_volume_percent / 100.0
                    self.endpoint_volume.SetMasterVolumeLevelScalar(scalar, None)
                except Exception as e:
                    logger.error(f"Failed to set system volume: {e}")
        else:
            action_desc = f"Volume Locked: {int(self.current_volume_percent)}%"

        return self.current_volume_percent, action_desc

    def reset_volume_anchor(self) -> None:
        """Resets the volume reference anchor when exiting gesture."""
        self.volume_anchor = None

    def adjust_brightness_continuous(self, curr_x: int, curr_y: int) -> Tuple[int, str]:
        """
        Rate-based continuous brightness adjustment (joystick style):
        - Captures initial hand position as anchor.
        - Tilting UP increases screen brightness continuously.
        - Tilting DOWN decreases screen brightness continuously.
        - Hand in center deadzone locks current brightness setting.
        """
        now = time.time()

        if self.brightness_anchor is None:
            self.brightness_anchor = (curr_x, curr_y)
            return self.current_brightness_percent, f"Brightness Ready: {self.current_brightness_percent}%"

        if now - self.last_update_time < config.CONTROL_UPDATE_INTERVAL:
            return self.current_brightness_percent, f"Brightness: {self.current_brightness_percent}%"

        self.last_update_time = now
        _, anchor_y = self.brightness_anchor
        dy = curr_y - anchor_y

        action_desc = f"Brightness: {self.current_brightness_percent}%"

        if abs(dy) > config.CONTROL_DEADZONE:
            offset = abs(dy) - config.CONTROL_DEADZONE
            step = (offset / 8.0) * 1.5 * config.CONTROL_SPEED_FACTOR

            if dy < 0:
                # Hand UP -> Brightness UP
                self.current_brightness_percent = min(100, int(self.current_brightness_percent + step))
                action_desc = f"▲ Brightness UP: {self.current_brightness_percent}%"
            else:
                # Hand DOWN -> Brightness DOWN
                self.current_brightness_percent = max(0, int(self.current_brightness_percent - step))
                action_desc = f"▼ Brightness DOWN: {self.current_brightness_percent}%"

            if SBC_AVAILABLE:
                try:
                    sbc.set_brightness(self.current_brightness_percent)
                except Exception as e:
                    logger.debug(f"Failed to set screen brightness: {e}")
        else:
            action_desc = f"Brightness Locked: {self.current_brightness_percent}%"

        return self.current_brightness_percent, action_desc

    def reset_brightness_anchor(self) -> None:
        """Resets the brightness reference anchor when exiting gesture."""
        self.brightness_anchor = None
