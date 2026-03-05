import json
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from .database import Base
from ..config import settings


class TaskType(str, Enum):
    UPDATE = "update"
    PACK = "pack"
    EXTRACT = "extract"
    CRC = "crc"
    JP_GL_CONVERT = "jp_gl_convert"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, index=True)
    session_uuid = Column(String, ForeignKey("sessions.uuid"), nullable=False, index=True)
    type = Column(SQLEnum(TaskType), nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    options = Column(Text)  # JSON string
    error_message = Column(Text)
    cli_log = Column(Text)  # CLI command output log
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationships
    session = relationship("Session", back_populates="tasks")
    files = relationship("File", back_populates="task")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
    
    def set_options(self, options: dict):
        """Set options from dict."""
        self.options = json.dumps(options)
    
    def get_options(self) -> dict:
        """Get options as dict."""
        return json.loads(self.options) if self.options else {}
    
    def mark_processing(self):
        """Mark task as processing."""
        self.status = TaskStatus.PROCESSING
    
    def mark_completed(self, cli_log: str = None):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if cli_log:
            self.cli_log = cli_log
    
    def mark_failed(self, error_message: str, cli_log: str = None):
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        if cli_log:
            self.cli_log = cli_log