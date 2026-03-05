from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship

from .database import Base
from ..config import settings


class Session(Base):
    __tablename__ = "sessions"
    
    uuid = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_accessed = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tasks = relationship("Task", back_populates="session", cascade="all, delete-orphan")
    files = relationship("File", back_populates="session", cascade="all, delete-orphan")
    
    def __init__(self, uuid: str, **kwargs):
        super().__init__(**kwargs)
        self.uuid = uuid
        self.expires_at = datetime.utcnow() + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
    
    def refresh(self):
        """Refresh session expiration time."""
        self.expires_at = datetime.utcnow() + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
        self.last_accessed = datetime.utcnow()
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at
