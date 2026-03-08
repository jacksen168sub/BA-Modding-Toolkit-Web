import asyncio
import re
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime


def extract_character_name(filename: str) -> str:
    """Extract character name from bundle filename."""
    if not filename:
        return "unknown"
    
    patterns = [
        r'spinelobbies-([a-zA-Z0-9_-]+?)-_mxdependency',
        r'spinecharacters-([a-zA-Z0-9_-]+?)-_mxprolog',
        r'spinebackground-([a-zA-Z0-9_-]+?)-_mxdependency',
        r'assets-_mx-spinecharacters-([a-zA-Z0-9_-]+?)-_mxdependency',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            name = match.group(1)
            # Format: xxx_yyy -> xxx(yyy)
            idx = name.rfind('_')
            if idx > 0:
                return f"{name[:idx]}({name[idx+1:]})"
            return name
    
    return "unknown"

from ..models.database import get_db
from ..models.task import TaskType, TaskStatus
from ..models.schemas import (
    TaskResponse, TaskBrief, TaskCreate, QueueInfo,
    UpdateTaskCreate, PackTaskCreate, ExtractTaskCreate, CrcTaskCreate,
    MessageResponse
)
from ..services.session_service import SessionService
from ..services.task_service import TaskService
from ..services.file_service import FileService
from ..services.cli_runner import cli_runner
from ..config import settings

router = APIRouter(prefix="/tasks", tags=["Tasks"])

# Semaphore to limit concurrent task execution
task_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)


def get_task_response(task, db: Session) -> TaskResponse:
    """Build task response with files and queue info."""
    file_service = FileService(db)
    task_service = TaskService(db)
    files = file_service.get_by_task(task.id)
    
    # Get queue info for pending/processing tasks
    queue_info = None
    if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        queue_data = task_service.get_queue_info(task.id, task.session_uuid)
        if queue_data:
            queue_info = QueueInfo(**queue_data)
    
    return TaskResponse(
        id=task.id,
        session_uuid=task.session_uuid,
        type=task.type,
        status=task.status,
        name=task.name,
        options=task.get_options(),
        error_message=task.error_message,
        cli_log=task.cli_log,
        created_at=task.created_at,
        completed_at=task.completed_at,
        expires_at=task.expires_at,
        files=[
            {
                "id": f.id,
                "session_uuid": f.session_uuid,
                "task_id": f.task_id,
                "type": f.type,
                "original_name": f.original_name,
                "size": f.size,
                "created_at": f.created_at,
                "download_url": f"/api/files/download/{f.id}"
            }
            for f in files
        ],
        queue_info=queue_info
    )


async def execute_update_task(task_id: str, session_uuid: str, options: dict):
    """Execute update task in background with concurrency control."""
    from ..models.database import SessionLocal
    
    # Wait for semaphore slot - this limits concurrent execution
    async with task_semaphore:
        db = SessionLocal()
        cli_log = ""
        try:
            task_service = TaskService(db)
            file_service = FileService(db)
            
            task = task_service.get(task_id)
            if not task:
                return
            
            task_service.update_status(task_id, TaskStatus.PROCESSING)
            
            # Get old mod file
            old_bundle_id = options.get("old_bundle_file_id")
            old_bundle_file = file_service.get(old_bundle_id)
            
            if not old_bundle_file:
                task_service.update_status(
                    task_id, TaskStatus.FAILED, 
                    "Old mod file not found"
                )
                return
            
            # Get target file (required)
            target_file_id = options.get("target_file_id")
            target_file = file_service.get(target_file_id) if target_file_id else None
            
            if not target_file:
                task_service.update_status(
                    task_id, TaskStatus.FAILED,
                    "Target game file not found. Please upload the new game resource bundle."
                )
                return
            
            # Create output directory
            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # Run CLI command
                output_path, cli_log = await cli_runner.run_update(
                    old_bundle=Path(old_bundle_file.stored_path),
                    output_dir=output_dir,
                    target_bundle=Path(target_file.stored_path),
                    crc_correction=options.get("crc_correction", True),
                    asset_types=options.get("asset_types", ["Texture2D", "TextAsset", "Mesh"])
                )
                
                # Create output file record - use target bundle's original name
                output_file = file_service.create_output_file(
                    session_uuid=session_uuid,
                    file_path=output_path,
                    original_name=target_file.original_name,
                    task_id=task_id
                )
                
                task_service.update_status(task_id, TaskStatus.COMPLETED, cli_log=cli_log)
                
            except RuntimeError as e:
                # Extract log from error if available
                if hasattr(e, 'args') and len(e.args) > 1:
                    cli_log = e.args[1] if isinstance(e.args[1], str) else str(e.args[1])
                task_service.update_status(task_id, TaskStatus.FAILED, str(e.args[0]) if e.args else str(e), cli_log=cli_log)
            except Exception as e:
                task_service.update_status(task_id, TaskStatus.FAILED, str(e), cli_log=cli_log)
                
        finally:
            db.close()


async def execute_pack_task(task_id: str, session_uuid: str, options: dict):
    """Execute pack task in background with concurrency control."""
    from ..models.database import SessionLocal
    
    async with task_semaphore:
        db = SessionLocal()
        cli_log = ""
        try:
            task_service = TaskService(db)
            file_service = FileService(db)
            
            task = task_service.get(task_id)
            if not task:
                return
            
            task_service.update_status(task_id, TaskStatus.PROCESSING)
            
            # Get target bundle file
            target_bundle_id = options.get("target_bundle_file_id")
            target_file = file_service.get(target_bundle_id)
            
            if not target_file:
                task_service.update_status(task_id, TaskStatus.FAILED, "Target bundle not found")
                return
            
            # Create asset folder from uploaded files
            asset_folder = settings.temp_path / session_uuid / task_id / "assets"
            asset_folder.mkdir(parents=True, exist_ok=True)
            
            # Copy uploaded asset files to temp folder
            asset_file_ids = options.get("asset_folder_files", [])
            for file_id in asset_file_ids:
                asset_file = file_service.get(file_id)
                if asset_file:
                    import shutil
                    shutil.copy(asset_file.stored_path, asset_folder / asset_file.original_name)
            
            # Create output directory
            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                output_path, cli_log = await cli_runner.run_pack(
                    asset_folder=asset_folder,
                    target_bundle=Path(target_file.stored_path),
                    output_dir=output_dir,
                    crc_correction=options.get("crc_correction", True)
                )
                
                # Use target bundle's original name for output
                output_file = file_service.create_output_file(
                    session_uuid=session_uuid,
                    file_path=output_path,
                    original_name=target_file.original_name,
                    task_id=task_id
                )
                
                task_service.update_status(task_id, TaskStatus.COMPLETED, cli_log=cli_log)
                
            except RuntimeError as e:
                if hasattr(e, 'args') and len(e.args) > 1:
                    cli_log = e.args[1] if isinstance(e.args[1], str) else str(e.args[1])
                task_service.update_status(task_id, TaskStatus.FAILED, str(e.args[0]) if e.args else str(e), cli_log=cli_log)
            except Exception as e:
                task_service.update_status(task_id, TaskStatus.FAILED, str(e), cli_log=cli_log)
                
        finally:
            db.close()


async def execute_extract_task(task_id: str, session_uuid: str, options: dict):
    """Execute extract task in background with concurrency control."""
    from ..models.database import SessionLocal
    
    async with task_semaphore:
        db = SessionLocal()
        cli_log = ""
        try:
            task_service = TaskService(db)
            file_service = FileService(db)
            
            task = task_service.get(task_id)
            if not task:
                return
            
            task_service.update_status(task_id, TaskStatus.PROCESSING)
            
            # Get bundle files
            bundle_file_ids = options.get("bundle_file_ids", [])
            bundle_paths = []
            for file_id in bundle_file_ids:
                bundle_file = file_service.get(file_id)
                if bundle_file:
                    bundle_paths.append(Path(bundle_file.stored_path))
            
            if not bundle_paths:
                task_service.update_status(task_id, TaskStatus.FAILED, "No bundle files found")
                return
            
            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                result_dir, cli_log = await cli_runner.run_extract(
                    bundle_paths=bundle_paths,
                    output_dir=output_dir,
                    asset_types=options.get("asset_types", ["Texture2D", "TextAsset", "Mesh"])
                )
                
                # Pack all extracted files into a zip
                import zipfile
                # Use first bundle's name for the zip file
                first_bundle_file = file_service.get(bundle_file_ids[0])
                zip_name = Path(first_bundle_file.original_name).stem + "_extracted.zip"
                # Create zip in parent directory to avoid including it in itself
                zip_path = output_dir.parent / zip_name
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for extracted_file in result_dir.rglob("*"):
                        if extracted_file.is_file():
                            rel_path = extracted_file.relative_to(result_dir)
                            zipf.write(extracted_file, rel_path)
                
                # Move zip to output directory
                final_zip_path = output_dir / zip_name
                import shutil
                shutil.move(str(zip_path), str(final_zip_path))
                zip_path = final_zip_path
                
                # Create single output file record for the zip
                file_service.create_output_file(
                    session_uuid=session_uuid,
                    file_path=zip_path,
                    original_name=zip_name,
                    task_id=task_id
                )
                
                task_service.update_status(task_id, TaskStatus.COMPLETED, cli_log=cli_log)
                
            except RuntimeError as e:
                if hasattr(e, 'args') and len(e.args) > 1:
                    cli_log = e.args[1] if isinstance(e.args[1], str) else str(e.args[1])
                task_service.update_status(task_id, TaskStatus.FAILED, str(e.args[0]) if e.args else str(e), cli_log=cli_log)
            except Exception as e:
                task_service.update_status(task_id, TaskStatus.FAILED, str(e), cli_log=cli_log)
                
        finally:
            db.close()


async def execute_crc_task(task_id: str, session_uuid: str, options: dict):
    """Execute CRC task in background with concurrency control."""
    from ..models.database import SessionLocal
    
    async with task_semaphore:
        db = SessionLocal()
        cli_log = ""
        try:
            task_service = TaskService(db)
            file_service = FileService(db)
            
            task = task_service.get(task_id)
            if not task:
                return
            
            task_service.update_status(task_id, TaskStatus.PROCESSING)
            
            modified_id = options.get("modified_file_id")
            original_id = options.get("original_file_id")
            
            modified_file = file_service.get(modified_id)
            original_file = file_service.get(original_id)
            
            if not modified_file:
                task_service.update_status(task_id, TaskStatus.FAILED, "Modified bundle file not found")
                return
            
            if not original_file:
                task_service.update_status(task_id, TaskStatus.FAILED, "Original bundle file not found")
                return
            
            try:
                output_path, cli_log = await cli_runner.run_crc(
                    modified_path=Path(modified_file.stored_path),
                    original_path=Path(original_file.stored_path),
                    no_backup=True  # Don't create backup in server environment
                )
                
                # Create output file record for the modified bundle
                output_file = file_service.create_output_file(
                    session_uuid=session_uuid,
                    file_path=output_path,
                    original_name=modified_file.original_name,
                    task_id=task_id
                )
                
                task_service.update_status(task_id, TaskStatus.COMPLETED, cli_log=cli_log)
                
            except RuntimeError as e:
                if hasattr(e, 'args') and len(e.args) > 1:
                    cli_log = e.args[1] if isinstance(e.args[1], str) else str(e.args[1])
                task_service.update_status(task_id, TaskStatus.FAILED, str(e.args[0]) if e.args else str(e), cli_log=cli_log)
            except Exception as e:
                task_service.update_status(task_id, TaskStatus.FAILED, str(e), cli_log=cli_log)
                
        finally:
            db.close()


@router.post("/update", response_model=TaskResponse)
def create_update_task(
    request: UpdateTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a mod update task."""
    session_service = SessionService(db)
    session = session_service.get(request.session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get file info to extract character name
    file_service = FileService(db)
    old_bundle_file = file_service.get(request.old_bundle_file_id)
    name = extract_character_name(old_bundle_file.original_name) if old_bundle_file else "unknown"
    
    task_service = TaskService(db)
    task = task_service.create(
        session_uuid=request.session_uuid,
        task_type=TaskType.UPDATE,
        options=request.model_dump(),
        name=name
    )
    
    background_tasks.add_task(
        execute_update_task,
        task.id,
        request.session_uuid,
        request.model_dump()
    )
    
    return get_task_response(task, db)


@router.post("/pack", response_model=TaskResponse)
def create_pack_task(
    request: PackTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a pack task."""
    session_service = SessionService(db)
    session = session_service.get(request.session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get file info to extract character name
    file_service = FileService(db)
    target_file = file_service.get(request.target_bundle_file_id)
    name = extract_character_name(target_file.original_name) if target_file else "unknown"
    
    task_service = TaskService(db)
    task = task_service.create(
        session_uuid=request.session_uuid,
        task_type=TaskType.PACK,
        options=request.model_dump(),
        name=name
    )
    
    background_tasks.add_task(
        execute_pack_task,
        task.id,
        request.session_uuid,
        request.model_dump()
    )
    
    return get_task_response(task, db)


@router.post("/extract", response_model=TaskResponse)
def create_extract_task(
    request: ExtractTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create an extract task."""
    session_service = SessionService(db)
    session = session_service.get(request.session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get file info to extract character name (use first bundle)
    file_service = FileService(db)
    name = "unknown"
    if request.bundle_file_ids:
        first_bundle = file_service.get(request.bundle_file_ids[0])
        if first_bundle:
            name = extract_character_name(first_bundle.original_name)
    
    task_service = TaskService(db)
    task = task_service.create(
        session_uuid=request.session_uuid,
        task_type=TaskType.EXTRACT,
        options=request.model_dump(),
        name=name
    )
    
    background_tasks.add_task(
        execute_extract_task,
        task.id,
        request.session_uuid,
        request.model_dump()
    )
    
    return get_task_response(task, db)


@router.post("/crc", response_model=TaskResponse)
def create_crc_task(
    request: CrcTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a CRC correction task.
    
    Requires both modified and original bundle files to perform CRC correction.
    """
    session_service = SessionService(db)
    session = session_service.get(request.session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get file info to extract character name
    file_service = FileService(db)
    modified_file = file_service.get(request.modified_file_id)
    name = extract_character_name(modified_file.original_name) if modified_file else "unknown"
    
    task_service = TaskService(db)
    task = task_service.create(
        session_uuid=request.session_uuid,
        task_type=TaskType.CRC,
        options=request.model_dump(),
        name=name
    )
    
    background_tasks.add_task(
        execute_crc_task,
        task.id,
        request.session_uuid,
        request.model_dump()
    )
    
    return get_task_response(task, db)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Get task status and details."""
    task_service = TaskService(db)
    task = task_service.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return get_task_response(task, db)


@router.get("/session/{session_uuid}", response_model=list[TaskBrief])
def list_session_tasks(session_uuid: str, db: Session = Depends(get_db)):
    """List all tasks for a session."""
    task_service = TaskService(db)
    file_service = FileService(db)
    tasks = task_service.get_by_session(session_uuid)
    
    result = []
    for task in tasks:
        files = file_service.get_by_task(task.id)
        
        # Get name: use existing name or extract from file
        name = task.name
        if not name and files:
            # Extract name from first file's original name
            name = extract_character_name(files[0].original_name)
        
        # Get queue info for pending/processing tasks
        queue_info = None
        if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
            queue_data = task_service.get_queue_info(task.id, session_uuid)
            if queue_data:
                queue_info = QueueInfo(**queue_data)
        
        result.append(TaskBrief(
            id=task.id,
            type=task.type,
            status=task.status,
            name=name,
            created_at=task.created_at,
            completed_at=task.completed_at,
            options=task.get_options(),
            files=[
                {
                    "id": f.id,
                    "session_uuid": f.session_uuid,
                    "task_id": f.task_id,
                    "type": f.type,
                    "original_name": f.original_name,
                    "size": f.size,
                    "created_at": f.created_at,
                    "download_url": f"/api/files/download/{f.id}"
                }
                for f in files
            ],
            queue_info=queue_info
        ))
    
    return result


@router.delete("/{task_id}", response_model=MessageResponse)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """Delete a task."""
    task_service = TaskService(db)
    
    if not task_service.delete(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    
    return MessageResponse(message="Task deleted successfully")


@router.get("/queue/status")
def get_queue_status(db: Session = Depends(get_db)):
    """Get task queue status (pending and processing counts)."""
    task_service = TaskService(db)
    pending_count = task_service.count_by_status(TaskStatus.PENDING)
    processing_count = task_service.count_by_status(TaskStatus.PROCESSING)
    
    return {
        "pending": pending_count,
        "processing": processing_count,
        "queue_length": pending_count + processing_count,
        "max_concurrent": settings.MAX_CONCURRENT_TASKS
    }