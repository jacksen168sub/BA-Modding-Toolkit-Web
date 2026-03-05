from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from ..models.database import get_db
from ..models.schemas import FileResponse as FileResponseSchema, MessageResponse
from ..models.file import FileType
from ..services.file_service import FileService
from ..services.session_service import SessionService
from ..config import settings

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload", response_model=FileResponseSchema)
async def upload_file(
    file: UploadFile = File(...),
    session_uuid: str = Form(...),
    db: Session = Depends(get_db)
):
    """Upload a file and associate with session."""
    # Validate session
    session_service = SessionService(db)
    session = session_service.get(session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check file size
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    await file.seek(0)  # Reset file pointer
    
    # Check file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )
    
    # Save file
    file_service = FileService(db)
    file_record = await file_service.save_upload(session_uuid, file)
    
    return FileResponseSchema(
        id=file_record.id,
        session_uuid=file_record.session_uuid,
        task_id=file_record.task_id,
        type=file_record.type,
        original_name=file_record.original_name,
        size=file_record.size,
        created_at=file_record.created_at,
        download_url=f"/api/files/download/{file_record.id}"
    )


@router.get("/download/{file_id}")
def download_file(file_id: str, db: Session = Depends(get_db)):
    """Download a file by ID."""
    file_service = FileService(db)
    file_record = file_service.get(file_id)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = Path(file_record.stored_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=file_path,
        filename=file_record.original_name,
        media_type="application/octet-stream"
    )


@router.get("/{file_id}", response_model=FileResponseSchema)
def get_file_info(file_id: str, db: Session = Depends(get_db)):
    """Get file information."""
    file_service = FileService(db)
    file_record = file_service.get(file_id)
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponseSchema(
        id=file_record.id,
        session_uuid=file_record.session_uuid,
        task_id=file_record.task_id,
        type=file_record.type,
        original_name=file_record.original_name,
        size=file_record.size,
        created_at=file_record.created_at,
        download_url=f"/api/files/download/{file_record.id}"
    )


@router.delete("/{file_id}", response_model=MessageResponse)
def delete_file(file_id: str, db: Session = Depends(get_db)):
    """Delete a file."""
    file_service = FileService(db)
    
    if not file_service.delete(file_id):
        raise HTTPException(status_code=404, detail="File not found")
    
    return MessageResponse(message="File deleted successfully")


@router.get("/session/{session_uuid}", response_model=list[FileResponseSchema])
def list_session_files(session_uuid: str, db: Session = Depends(get_db)):
    """List all files for a session."""
    file_service = FileService(db)
    files = file_service.get_by_session(session_uuid)
    
    return [
        FileResponseSchema(
            id=f.id,
            session_uuid=f.session_uuid,
            task_id=f.task_id,
            type=f.type,
            original_name=f.original_name,
            size=f.size,
            created_at=f.created_at,
            download_url=f"/api/files/download/{f.id}"
        )
        for f in files
    ]
