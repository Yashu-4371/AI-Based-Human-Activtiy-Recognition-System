"""
The server cannot force a browser to play audio. This module's only
responsibility is to decide WHETHER an alarm should sound for a given
alert (based on the system setting toggle) and expose that as a flag
that gets pushed to the frontend over the /ws/live WebSocket, where
the actual <audio> playback happens.
"""

from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting


def should_play_alarm(db: Session) -> bool:
    setting = db.query(SystemSetting).filter(SystemSetting.key == "alarm_sound_enabled").first()
    if not setting:
        return True
    return setting.value.strip().lower() == "true"
