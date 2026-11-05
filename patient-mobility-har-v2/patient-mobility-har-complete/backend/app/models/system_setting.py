"""System settings table: a simple key-value store for runtime-editable configuration
(alert thresholds, alarm sound choice, theme default, etc.) that shouldn't require
a redeploy to change, unlike values in .env.
"""

from sqlalchemy import Column, Integer, String

from app.database.session import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(120), unique=True, nullable=False, index=True)
    value = Column(String(500), nullable=False)
