import uuid as uuid_lib
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import UploadFile

from ..models.file import File, FileType
from ..config import settings


class FileService:
    def __init__(self, db: Session):
        self.db = db
    
    def _get_user_upload_dir(self, session_uuid: str) -> Path:
        """Get user's upload directory path."""
        path = settings.upload_path / session_uuid
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def _get_user_output_dir(self, session_uuid: str) -> Path:
        """Get user's output directory path."""
        path = settings.output_path / session_uuid
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    async def save_upload(
        self, 
        session_uuid: str, 
        upload_file: UploadFile,
        task_id: Optional[str] = None
    ) -> File:
        """Save uploaded file and create database record."""
        # Generate unique file ID
        file_id = str(uuid_lib.uuid4())
        
        # Determine file extension and stored name
        original_name = upload_file.filename or "unknown"
        suffix = Path(original_name).suffix
        
        # Create stored filename
        stored_name = f"{file_id}{suffix}"
        stored_path = self._get_user_upload_dir(session_uuid) / stored_name
        
        # Save file to disk
        with open(stored_path, "wb") as buffer:
            content = await upload_file.read()
            buffer.write(content)
        
        # Get file size
        file_size = stored_path.stat().st_size
        
        # Create database record
        file_record = File(
            id=file_id,
            session_uuid=session_uuid,
            task_id=task_id,
            type=FileType.INPUT,
            original_name=original_name,
            stored_path=str(stored_path),
            size=file_size
        )
        
        self.db.add(file_record)
        self.db.commit()
        self.db.refresh(file_record)
        
        return file_record
    
    def create_output_file(
        self,
        session_uuid: str,
        file_path: Path,
        original_name: str,
        task_id: Optional[str] = None
    ) -> File:
        """Create database record for output file."""
        file_id = str(uuid_lib.uuid4())
        
        # Move file to output directory
        output_dir = self._get_user_output_dir(session_uuid)
        suffix = file_path.suffix
        new_path = output_dir / f"{file_id}{suffix}"
        
        if file_path.exists():
            shutil.move(str(file_path), str(new_path))
        
        file_record = File(
            id=file_id,
            session_uuid=session_uuid,
            task_id=task_id,
            type=FileType.OUTPUT,
            original_name=original_name,
            stored_path=str(new_path),
            size=new_path.stat().st_size if new_path.exists() else 0
        )
        
        self.db.add(file_record)
        self.db.commit()
        self.db.refresh(file_record)
        
        return file_record
    
    def get(self, file_id: str) -> Optional[File]:
        """Get file by ID."""
        return self.db.query(File).filter(File.id == file_id).first()
    
    def get_by_session(self, session_uuid: str) -> List[File]:
        """Get all files for a session."""
        return self.db.query(File).filter(File.session_uuid == session_uuid).all()
    
    def get_by_task(self, task_id: str) -> List[File]:
        """Get all files for a task."""
        return self.db.query(File).filter(File.task_id == task_id).all()
    
    def delete(self, file_id: str) -> bool:
        """Delete file record and physical file."""
        file = self.get(file_id)
        if file:
            # Delete physical file
            path = Path(file.stored_path)
            if path.exists():
                path.unlink()
            
            # Delete database record
            self.db.delete(file)
            self.db.commit()
            return True
        return False
    
    def delete_user_files(self, session_uuid: str):
        """Delete all files for a user session."""
        # Delete physical directories
        upload_dir = self._get_user_upload_dir(session_uuid)
        output_dir = self._get_user_output_dir(session_uuid)
        
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
        if output_dir.exists():
            shutil.rmtree(output_dir)
