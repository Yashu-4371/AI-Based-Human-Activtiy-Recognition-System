"""
Wraps cv2.VideoCapture to support webcam index, USB device, IP camera
HTTP stream, and RTSP URL sources through one uniform interface, with
automatic reconnect-with-backoff if frame reads start failing.
"""

import time
from typing import Optional

import cv2
import numpy as np

from app.models.camera_setting import CameraSourceType
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_RECONNECT_BACKOFF_SEC = 10.0


class CameraManager:
    def __init__(self, source_type: CameraSourceType, source_uri: str, width: int = 640, height: int = 480):
        self.source_type = source_type
        self.source_uri = source_uri
        self.width = width
        self.height = height
        self._capture: Optional[cv2.VideoCapture] = None
        self._consecutive_failures = 0

    def _resolve_source(self):
        # Webcam/USB sources are typically referenced by integer index.
        if self.source_type in (CameraSourceType.webcam, CameraSourceType.usb):
            try:
                return int(self.source_uri)
            except ValueError:
                return self.source_uri
        return self.source_uri  # IP / RTSP: full URL string

    def open(self) -> bool:
        source = self._resolve_source()
        self._capture = cv2.VideoCapture(source)
        if self.width:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        is_opened = self._capture.isOpened()
        if is_opened:
            logger.info("Camera opened: type=%s source=%s", self.source_type, self.source_uri)
            self._consecutive_failures = 0
        else:
            logger.error("Failed to open camera: type=%s source=%s", self.source_type, self.source_uri)
        return is_opened

    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def read_frame(self) -> Optional[np.ndarray]:
        """Reads one frame; returns None and attempts reconnect-with-backoff on repeated failure."""
        if not self.is_open():
            if not self._attempt_reconnect():
                return None

        success, frame = self._capture.read()
        if not success or frame is None:
            self._consecutive_failures += 1
            logger.warning("Frame read failed (consecutive_failures=%d)", self._consecutive_failures)
            if self._consecutive_failures >= 5:
                self._attempt_reconnect()
            return None

        self._consecutive_failures = 0
        return frame

    def _attempt_reconnect(self) -> bool:
        backoff = min(2 ** min(self._consecutive_failures, 4), _MAX_RECONNECT_BACKOFF_SEC)
        logger.info("Attempting camera reconnect in %.1fs...", backoff)
        time.sleep(backoff)
        self.release()
        return self.open()

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
