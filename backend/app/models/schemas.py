from datetime import datetime
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, field_validator
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


class QueueInfo(BaseModel):
    """Queue position information for a task."""
    user_position: Optional[int] = None  # Position in user's own queue (1-based)
    user_queue_length: int = 0  # Total pending tasks for this user
    global_position: Optional[int] = None  # Position in global queue (1-based)
    global_queue_length: int = 0  # Total pending tasks globally


class TaskResponse(BaseModel):
    id: str
    session_uuid: str
    type: TaskType
    status: TaskStatus
    name: Optional[str] = None  # Character name extracted from filename
    options: dict
    error_message: Optional[str]
    cli_log: Optional[str] = None  # CLI command output log
    created_at: datetime
    completed_at: Optional[datetime]
    expires_at: datetime
    files: List[FileResponse] = []
    queue_info: Optional[QueueInfo] = None  # Queue position info for pending/processing tasks
    
    class Config:
        from_attributes = True


class TaskBrief(BaseModel):
    """Brief task info for listing."""
    id: str
    type: TaskType
    status: TaskStatus
    name: Optional[str] = None  # Character name extracted from filename
    created_at: datetime
    completed_at: Optional[datetime]
    options: dict = {}  # 包含文件名信息
    files: List[FileResponse] = []
    queue_info: Optional[QueueInfo] = None  # Queue position info for pending/processing tasks
    
    class Config:
        from_attributes = True


# Update task specific schemas
class UpdateTaskCreate(BaseModel):
    session_uuid: str
    # Single mode (backward compatible)
    old_bundle_file_id: Optional[str] = None      # Old mod file
    target_file_id: Optional[str] = None           # New game resource bundle
    # Batch mode
    old_bundle_file_ids: List[str] = []            # Multiple old mod files
    target_file_ids: List[str] = []                # Multiple target game resource files
    # Common options
    crc_correction: bool = True
    asset_types: List[str] = ["Texture2D", "TextAsset", "Mesh"]
    strategy: str = "path_id"     # Match strategy: path_id, cont_name_type, name_type
    compression: str = "lzma"     # Compression method: lzma, lz4, original, none

    @field_validator('strategy')
    @classmethod
    def validate_strategy(cls, v):
        if v not in ('path_id', 'cont_name_type', 'name_type'):
            raise ValueError('strategy must be one of: path_id, cont_name_type, name_type')
        return v

    @field_validator('compression')
    @classmethod
    def validate_compression(cls, v):
        if v not in ('lzma', 'lz4', 'original', 'none'):
            raise ValueError('compression must be one of: lzma, lz4, original, none')
        return v

    def is_batch(self) -> bool:
        """Check if this is a batch update request."""
        return bool(self.old_bundle_file_ids and self.target_file_ids)


# Pack task specific schemas
class PackTaskCreate(BaseModel):
    session_uuid: str
    asset_folder_files: List[str] = []  # List of uploaded asset file IDs
    target_bundle_file_id: str
    crc_correction: bool = True
    compression: str = "lzma"     # Compression method: lzma, lz4, original, none

    @field_validator('compression')
    @classmethod
    def validate_compression(cls, v):
        if v not in ('lzma', 'lz4', 'original', 'none'):
            raise ValueError('compression must be one of: lzma, lz4, original, none')
        return v


# Extract task specific schemas
class ExtractTaskCreate(BaseModel):
    session_uuid: str
    bundle_file_ids: List[str] = []  # Support multiple bundles
    asset_types: List[str] = ["Texture2D", "TextAsset", "Mesh"]
    unpack_atlas: bool = False       # Unpack Atlas into individual PNG frames


# CRC task specific schemas
class CrcTaskCreate(BaseModel):
    session_uuid: str
    modified_file_id: str   # Modified bundle file (to be fixed)
    original_file_id: str   # Original bundle file (provides target CRC)
    check_only: bool = False  # Only calculate and compare CRC, do not modify files


# Split task specific schemas
class SplitTaskCreate(BaseModel):
    """Split: distribute legacy bundle assets to multiple modern bundles (one-to-many)."""
    session_uuid: str
    legacy_file_id: str          # Legacy bundle file
    modern_file_ids: List[str] = []  # Modern bundle file list
    crc_correction: bool = True
    asset_types: List[str] = ["Texture2D", "TextAsset", "Mesh"]
    compression: str = "lzma"

    @field_validator('compression')
    @classmethod
    def validate_compression(cls, v):
        if v not in ('lzma', 'lz4', 'original', 'none'):
            raise ValueError('compression must be one of: lzma, lz4, original, none')
        return v


# Merge task specific schemas
class MergeTaskCreate(BaseModel):
    """Merge: merge multiple modern bundle assets into a legacy bundle (many-to-one)."""
    session_uuid: str
    legacy_file_id: str          # Legacy bundle file (as base)
    modern_file_ids: List[str] = []  # Modern bundle file list
    crc_correction: bool = True
    asset_types: List[str] = ["Texture2D", "TextAsset", "Mesh"]
    compression: str = "lzma"

    @field_validator('compression')
    @classmethod
    def validate_compression(cls, v):
        if v not in ('lzma', 'lz4', 'original', 'none'):
            raise ValueError('compression must be one of: lzma, lz4, original, none')
        return v


# API Response schemas
class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str


# Service status schemas
class ServiceInfo(BaseModel):
    """Identity and liveness of the running backend."""
    name: str
    version: Optional[str] = None
    commit: Optional[str] = None
    status: str  # healthy | degraded
    uptime_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    server_time: datetime


class TaskStats(BaseModel):
    """Lifetime task counters."""
    total: int
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    success_rate: Optional[float] = None  # completed / finished, as a percentage
    avg_duration_seconds: Optional[float] = None
    recent: Dict[str, int]  # last_hour / last_24h / last_7d


class QueueStats(BaseModel):
    """Current queue depth against the worker limit."""
    pending: int
    processing: int
    length: int
    max_concurrent: int
    available_slots: int
    utilization: float  # percentage of worker slots in use


class ContainerInfo(BaseModel):
    """Container runtime and the resource limits applied to this process."""
    detected: bool
    runtime: Optional[str] = None  # docker | podman | kubernetes
    cgroup_version: Optional[int] = None
    cpu_quota: Optional[float] = None  # whole cores, None when unlimited
    memory_limit: Optional[int] = None  # bytes, None when unlimited


class CpuStats(BaseModel):
    percent: Optional[float] = None
    cores: Optional[int] = None  # effective cores (container quota or host)
    host_cores: Optional[int] = None
    quota: Optional[float] = None
    load_avg: Optional[List[float]] = None


class MemoryStats(BaseModel):
    total: Optional[int] = None
    used: Optional[int] = None
    available: Optional[int] = None
    percent: Optional[float] = None
    host_total: Optional[int] = None
    limit: Optional[int] = None  # container memory limit, None when unlimited


class DiskStats(BaseModel):
    path: Optional[str] = None
    total: Optional[int] = None
    used: Optional[int] = None
    free: Optional[int] = None
    percent: Optional[float] = None


class ProcessStats(BaseModel):
    """The backend process itself, as opposed to the whole host."""
    pid: Optional[int] = None
    memory_rss: Optional[int] = None
    cpu_percent: Optional[float] = None
    threads: Optional[int] = None
    started_at: Optional[datetime] = None


class SystemStats(BaseModel):
    container: ContainerInfo
    cpu: CpuStats
    memory: MemoryStats
    disk: DiskStats
    process: ProcessStats


class StorageBucket(BaseModel):
    count: Optional[int] = None
    size: Optional[int] = None


class StorageStats(BaseModel):
    uploads: StorageBucket
    outputs: StorageBucket
    total_size: Optional[int] = None


class SessionStats(BaseModel):
    total: Optional[int] = None
    active: Optional[int] = None


class ServiceStatus(BaseModel):
    """Full service status snapshot."""
    service: ServiceInfo
    tasks: TaskStats
    queue: QueueStats
    system: SystemStats
    storage: StorageStats
    sessions: SessionStats
    redacted: List[str] = []  # sections blanked out by STATUS_REDACT


# Update forward references
SessionWithTasks.model_rebuild()
TaskResponse.model_rebuild()