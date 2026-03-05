import uuid as uuid_lib
from typing import Optional
from sqlalchemy.orm import Session

from ..models.session import Session
from ..models.task import Task


class SessionService:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, uuid: Optional[str] = None) -> Session:
        """Create a new session."""
        if uuid is None:
            uuid = str(uuid_lib.uuid4())
        
        session = Session(uuid=uuid)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def get(self, uuid: str) -> Optional[Session]:
        """Get session by UUID."""
        return self.db.query(Session).filter(Session.uuid == uuid).first()
    
    def get_or_create(self, uuid: str) -> Session:
        """Get existing session or create new one."""
        session = self.get(uuid)
        if session:
            session.refresh()
            self.db.commit()
            return session
        return self.create(uuid)
    
    def refresh(self, uuid: str) -> Optional[Session]:
        """Refresh session expiration time."""
        session = self.get(uuid)
        if session:
            session.refresh()
            self.db.commit()
        return session
    
    def delete(self, uuid: str) -> bool:
        """Delete session and all related data."""
        session = self.get(uuid)
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False
    
    def get_tasks(self, uuid: str) -> list[Task]:
        """Get all tasks for a session."""
        session = self.get(uuid)
        if session:
            return session.tasks
        return []
