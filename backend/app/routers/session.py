from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.schemas import SessionResponse, SessionWithTasks, MessageResponse
from ..services.session_service import SessionService

router = APIRouter(prefix="/session", tags=["Session"])


@router.get("/{uuid}", response_model=SessionWithTasks)
def get_session(uuid: str, db: Session = Depends(get_db)):
    """Get session info with tasks list."""
    service = SessionService(db)
    session = service.get_or_create(uuid)
    
    return SessionWithTasks(
        uuid=session.uuid,
        created_at=session.created_at,
        expires_at=session.expires_at,
        tasks=[
            {
                "id": task.id,
                "type": task.type,
                "status": task.status,
                "created_at": task.created_at,
                "completed_at": task.completed_at
            }
            for task in session.tasks
        ]
    )


@router.post("/{uuid}/refresh", response_model=SessionResponse)
def refresh_session(uuid: str, db: Session = Depends(get_db)):
    """Refresh session expiration time."""
    service = SessionService(db)
    session = service.refresh(uuid)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session


@router.delete("/{uuid}", response_model=MessageResponse)
def delete_session(uuid: str, db: Session = Depends(get_db)):
    """Delete session and all associated data."""
    service = SessionService(db)
    
    if not service.delete(uuid):
        raise HTTPException(status_code=404, detail="Session not found")
    
    return MessageResponse(message="Session deleted successfully")
