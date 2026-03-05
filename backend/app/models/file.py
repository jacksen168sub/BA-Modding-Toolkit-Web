from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from .database import Base
from ..config import settings


class FileType(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


class File(Base):
    __tablename__ = "files"
    
    id = Column(String, primary_key=True, index=True)
    session_uuid = Column(String, ForeignKey("sessions.uuid"), nullable=False, index=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    type = Column(SQLEnum(FileType), nullable=False)
    original_name = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    session = relationship("Session", back_populates="files")
    task = relationship("Task", back_populates="files")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
