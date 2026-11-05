"""
Reads/writes the SystemSetting key-value table: runtime-editable
config (detection thresholds, alarm sound, theme) that the Settings
page lets an admin change without touching .env or redeploying.

Detection thresholds (fall/inactivity) are seeded from app/config.py
defaults on first startup (see init_db.py) but from then on the
DATABASE row is the source of truth — app/config.py values are only
the fallback used if a row is somehow missing.
"""

from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.system_setting import SystemSetting


def get_all(db: Session) -> Dict[str, str]:
    return {row.key: row.value for row in db.query(SystemSetting).all()}


def get_raw(db: Session, key: str) -> Optional[str]:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return row.value if row else None


def get_float(db: Session, key: str, default: float) -> float:
    raw = get_raw(db, key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def get_bool(db: Session, key: str, default: bool) -> bool:
    raw = get_raw(db, key)
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def set_many(db: Session, items: Dict[str, str]) -> Dict[str, str]:
    for key, value in items.items():
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
    db.commit()
    return get_all(db)
