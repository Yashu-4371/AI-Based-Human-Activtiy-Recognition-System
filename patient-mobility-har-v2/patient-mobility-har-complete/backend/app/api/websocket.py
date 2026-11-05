"""
/ws/live — pushes the current monitoring state (activity label,
confidence, skeleton points, FPS, alert flags) to any connected
dashboard, roughly at the camera's target frame rate. The video frame
itself (JPEG bytes) is sent as a separate base64 field so the client
can render both the overlay and the image from one message.
"""

import asyncio
import base64

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.camera.frame_buffer import live_frame_buffer
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

_PUSH_INTERVAL_SEC = 1 / 15  # matches default CAMERA_TARGET_FPS


@router.websocket("/ws/live")
async def websocket_live_feed(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected to /ws/live")

    try:
        while True:
            state = live_frame_buffer.get_state()

            payload = {
                "activity_label": state.activity_label,
                "confidence": state.confidence,
                "skeleton_points": state.skeleton_points,
                "fps": round(state.fps, 1),
                "fall_detected": state.fall_detected,
                "inactivity_warning": state.inactivity_warning,
                "camera_connected": state.camera_connected,
                "updated_at": state.updated_at.isoformat() if state.updated_at else None,
                "frame_jpeg_base64": base64.b64encode(state.jpeg_bytes).decode("utf-8") if state.jpeg_bytes else None,
            }

            await websocket.send_json(payload)
            await asyncio.sleep(_PUSH_INTERVAL_SEC)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /ws/live")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
