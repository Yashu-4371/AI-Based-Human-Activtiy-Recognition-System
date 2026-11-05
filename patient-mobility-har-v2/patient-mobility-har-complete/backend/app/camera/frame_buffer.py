"""
Thread-safe store for the most recent frame's derived state (JPEG bytes,
skeleton points, activity label/confidence, FPS, alert flags). The
monitoring pipeline writes to this on every processed frame; the
WebSocket route and the MJPEG-style live-view endpoint read from it.
Neither the HTTP layer nor the frontend ever touches raw OpenCV objects.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple


@dataclass
class LiveState:
    jpeg_bytes: Optional[bytes] = None
    skeleton_points: List[Tuple[float, float]] = field(default_factory=list)
    activity_label: Optional[str] = None
    confidence: float = 0.0
    fps: float = 0.0
    fall_detected: bool = False
    inactivity_warning: bool = False
    camera_connected: bool = False
    updated_at: Optional[datetime] = None


class FrameBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = LiveState()

    def update(self, **kwargs) -> None:
        with self._lock:
            for key, value in kwargs.items():
                setattr(self._state, key, value)
            self._state.updated_at = datetime.utcnow()

    def get_state(self) -> LiveState:
        with self._lock:
            # Return a shallow copy so callers don't hold the lock while reading.
            return LiveState(**self._state.__dict__)


# Module-level singleton — one active monitoring session per backend process,
# matching the project's current single-camera-session scope.
live_frame_buffer = FrameBuffer()
