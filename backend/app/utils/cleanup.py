import shutil
from datetime import datetime
from pathlib import Path
from typing import List
from sqlalchemy.orm import Session

from ..models.database import SessionLocal
from ..models.session import Session
from ..config import settings


def cleanup_expired_sessions(db: Session) -> List[str]:
    """
    Clean up expired sessions and their associated files.
    
    Returns:
        List of deleted session UUIDs
    """
    now = datetime.utcnow()
    
    # Find expired sessions
    expired_sessions = db.query(Session).filter(
        Session.expires_at < now
    ).all()
    
    deleted_uuids = []
    
    for session in expired_sessions:
        uuid = session.uuid
        
        # Delete user files
        upload_dir = settings.upload_path / uuid
        output_dir = settings.output_path / uuid
        
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
        
        if output_dir.exists():
            shutil.rmtree(output_dir)
        
        # Delete database record (cascade deletes tasks and files)
        db.delete(session)
        deleted_uuids.append(uuid)
    
    if deleted_uuids:
        db.commit()
    
    return deleted_uuids


def cleanup_temp_files():
    """Clean up temporary files older than 1 hour."""
    temp_dir = settings.temp_path
    if not temp_dir.exists():
        return
    
    now = datetime.utcnow().timestamp()
    one_hour_ago = now - 3600
    
    for item in temp_dir.iterdir():
        if item.stat().st_mtime < one_hour_ago:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)


async def periodic_cleanup():
    """
    Periodic cleanup task to be run in background.
    Should be called by scheduler or lifespan hook.
    """
    db = SessionLocal()
    try:
        deleted = cleanup_expired_sessions(db)
        if deleted:
            print(f"[Cleanup] Deleted {len(deleted)} expired sessions: {deleted}")
        
        cleanup_temp_files()
        print("[Cleanup] Temporary files cleaned")
    finally:
        db.close()
