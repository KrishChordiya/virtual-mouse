# Gesture-Controlled Virtual Mouse

A real-time, touchless, computer-vision-based virtual mouse implemented in Python using OpenCV, Google MediaPipe, and PyAutoGUI.

Developed as a final-year undergraduate project, this application enables users to control desktop cursor movement, mouse clicks, drag-and-drop, multi-item selection, scrolling, system volume, and screen brightness purely through natural webcam hand gestures.

---

## Features

- **Smooth Cursor Navigation**: Tracks the index fingertip with Exponential Moving Average (EMA) smoothing and margin scaling.
- **Single Left Click & Double Click**: Natural pinch gesture with temporal debouncing.
- **Single Right Click**: Middle-to-thumb pinch for context menus.
- **Drag and Drop**: Held pinch maintains mouse down, allowing dragging files and windows across screens/folders.
- **Multiple Selection**: Dedicated gesture for box/marquee multi-item selection.
- **Dynamic Vertical & Horizontal Scrolling**: Dual-finger gestures with dynamic speed based on displacement.
- **Continuous Volume Control**: Shaka gesture smoothly adjusts system audio volume with visual feedback.
- **Continuous Brightness Control**: Three-finger gesture smoothly adjusts screen brightness.
- **Failsafe Neutral Gesture**: Open hand immediately releases held mouse buttons and halts continuous adjustments.
- **On-Screen Display (HUD)**: Real-time visual feedback showing current mode, FPS, and dynamic progress bars.

---

## Gesture Cheat Sheet

| Gesture | Pose | Action |
|---|---|---|
| **Neutral / Idle** | 🖐️ Open Hand (All 5 fingers up) | Halts operations, releases held mouse buttons |
| **Cursor Move** | ☝️ Index finger UP only | Moves cursor smoothly across screen |
| **Left Click** | 🤏 Thumb + Index pinch (< 0.35s) | Single left click |
| **Double Click** | 🤏 Thumb + Index pinch double-tap | Double left click |
| **Right Click** | ✌️ Thumb + Middle pinch | Single right click |
| **Drag & Drop** | ✊ Thumb + Index pinch held (> 0.35s) | Holds left button down to drag; release to drop |
| **Multi-Select** | 🤘 Horns (Index + Pinky UP) | Box drag / Multi-select files |
| **Vertical Scroll** | ✌️ Two fingers UP (Index + Middle) | Move hand Up/Down to scroll page |
| **Horizontal Scroll**| ✌️ Two fingers UP moving sideways | Move hand Left/Right to scroll page |
| **Volume Control** | 🤙 Shaka (Thumb + Pinky UP) | Hand vertical height adjusts volume ($0-100\%$) |
| **Brightness** | 🖐️ Three fingers UP (Index + Middle + Ring) | Hand vertical height adjusts brightness ($0-100\%$) |

---

## Requirements & Environment

- Windows 10 or 11
- Webcam (built-in or external USB)
- [uv](https://docs.astral.sh/uv/) (Fast Python package manager)

---

## Installation & Running

1. Clone or navigate to the project directory:
   ```bash
   cd virtual-mouse
   ```

2. Run the application directly with `uv`:
   ```bash
   uv run virtual-mouse
   ```
   or:
   ```bash
   uv run python -m virtual_mouse.main
   ```

3. Press **`Q`** or **`Esc`** at any time to safely exit the application.
