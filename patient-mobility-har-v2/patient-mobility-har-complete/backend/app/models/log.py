"""Log table: persisted audit/debug trail for critical system events."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime

from app.database.session import Base


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    module = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
