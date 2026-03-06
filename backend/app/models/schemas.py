from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from .task import TaskType, TaskStatus
from .file import FileType


# Session schemas
class SessionResponse(BaseModel):
    uuid: str
    created_at: datetime
    expires_at: datetime
    last_accessed: datetime
    
    class Config:
        from_attributes = True


class SessionWithTasks(BaseModel):
    uuid: str
    created_at: datetime
    expires_at: datetime
    tasks: List["TaskResponse"] = []
    
    class Config:
        from_attributes = True


# File schemas
class FileUploadRequest(BaseModel):
    session_uuid: str


class FileResponse(BaseModel):
    id: str
    session_uuid: str
    task_id: Optional[str]
    type: FileType
    original_name: str
    size: int
    created_at: datetime
    download_url: Optional[str] = None
    
    class Config:
        from_attributes = True


# Task schemas
class TaskCreate(BaseModel):
    session_uuid: str
    type: TaskType
    options: dict = {}


class TaskResponse(BaseModel):
    id: str
    session_uuid: str
    type: TaskType
    status: TaskStatus
    options: dict
    error_message: Optional[str]
    cli_log: Optional[str] = None  # CLI command output log
    created_at: datetime
    completed_at: Optional[datetime]
    expires_at: datetime
    files: List[FileResponse] = []
    
    class Config:
        from_attributes = True


class TaskBrief(BaseModel):
    """Brief task info for listing."""
    id: str
    type: TaskType
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime]
    options: dict = {}  # 包含文件名信息
    files: List[FileResponse] = []
    
    class Config:
        from_attributes = True


# Update task specific schemas
class UpdateTaskCreate(BaseModel):
    session_uuid: str
    old_bundle_file_id: str      # Old mod file
    target_file_id: str           # New game resource bundle (required)
    crc_correction: bool = True
    asset_types: List[str] = ["Texture2D", "TextAsset", "Mesh"]


# Pack task specific schemas
class PackTaskCreate(BaseModel):
    session_uuid: str
    asset_folder_files: List[str] = []  # List of uploaded asset file IDs
    target_bundle_file_id: str
    crc_correction: bool = True


# Extract task specific schemas
class ExtractTaskCreate(BaseModel):
    session_uuid: str
    bundle_file_ids: List[str] = []  # Support multiple bundles
    asset_types: List[str] = ["Texture2D", "TextAsset", "Mesh"]


# CRC task specific schemas
class CrcTaskCreate(BaseModel):
    session_uuid: str
    modified_file_id: str   # Modified bundle file (to be fixed)
    original_file_id: str   # Original bundle file (provides target CRC)


# API Response schemas
class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str


# Update forward references
SessionWithTasks.model_rebuild()
TaskResponse.model_rebuild()