# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

import asyncio
import re
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime


def extract_character_name(filename: str) -> str:
    """Extract a short character label from a BA bundle filename (e.g. "yuuka(home)").

    Delegates to the vendored copy of the kernel's naming rules (app/services/naming.py).
    Returns "unknown" for names that do not look like a bundle (no mx marker), matching the
    previous behaviour so callers can still filter it out.
    """
    if not filename:
        return "unknown"
    if not re.search(r'mx(?:dependency|prolog|load)', filename, re.IGNORECASE):
        return "unknown"
    core = parse_filename(filename).core
    if not core:
        return "unknown"
    return display_name_from_core(core)


def _create_named_link(stored_path: Path, original_name: str, link_dir: Path) -> Path:
    """Create a hard link or copy with the original filename so the CLI can extract CRC from it.
    
    The upstream BAMT core extracts target CRC from the output filename via parse_filename().
    UUID-based filenames (e.g., 0d821ecc-14b4-4063-92a9-77f947f1d02c.bundle) don't contain
    CRC info, causing CRC correction to fail. This function creates a link with the original
    filename so the CRC extraction works correctly.
    
    Args:
        stored_path: The actual stored file path (UUID-named)
        original_name: The original filename with CRC info
        link_dir: Directory to create the link in
    
    Returns:
        Path to the created link
    """
    link_dir.mkdir(parents=True, exist_ok=True)
    link_path = link_dir / original_name
    
    if link_path.exists():
        link_path.unlink()
    
    try:
        # Try hard link first (most efficient, same filesystem)
        os.link(str(stored_path), str(link_path))
    except OSError:
        # Fall back to copy (cross-filesystem or permission issues)
        shutil.copy2(str(stored_path), str(link_path))
    
    return link_path


def _extract_character_from_filename(filename: str) -> str:
    """Extract the character core from a BA bundle filename (e.g. "yuuka_home").

    Delegates to the vendored copy of the kernel's naming rules (app/services/naming.py).
    Falls back to the filename stem if no core can be parsed.
    """
    return parse_filename(filename).core or filename.rsplit('.', 1)[0]


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
from ..services.naming import display_name_from_core, parse_filename
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
    """Execute an update task in the background with concurrency control.

    One pooled N-to-N run: every source file's assets are pooled by the kernel and applied
    to every target. Accepts both the batch arrays (old_bundle_file_ids / target_file_ids)
    and the legacy single ids (old_bundle_file_id / target_file_id).
    """
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

            source_ids = options.get("old_bundle_file_ids") or (
                [options["old_bundle_file_id"]] if options.get("old_bundle_file_id") else []
            )
            target_ids = options.get("target_file_ids") or (
                [options["target_file_id"]] if options.get("target_file_id") else []
            )
            sources = [f for f in (file_service.get(fid) for fid in source_ids) if f]
            targets = [f for f in (file_service.get(fid) for fid in target_ids) if f]

            if not sources:
                task_service.update_status(task_id, TaskStatus.FAILED, "Old mod file(s) not found")
                return
            if not targets:
                task_service.update_status(
                    task_id, TaskStatus.FAILED,
                    "Target game file(s) not found. Please upload the new game resource bundle(s)."
                )
                return

            # Each target becomes an output named after it, so duplicate names would collide.
            target_names = [t.original_name for t in targets]
            if len(set(target_names)) != len(target_names):
                task_service.update_status(
                    task_id, TaskStatus.FAILED,
                    "Duplicate target filenames are not supported; upload each target bundle only once."
                )
                return

            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)

            # Named links let the kernel read the target CRC from the output filename. Each
            # target gets its own subdir so same-named links can never clobber each other.
            link_root = output_dir / "_links"
            target_links = [
                _create_named_link(Path(t.stored_path), t.original_name, link_root / str(i))
                for i, t in enumerate(targets)
            ]

            try:
                output_paths, cli_log = await cli_runner.run_update(
                    source_files=[Path(s.stored_path) for s in sources],
                    target_files=target_links,
                    output_dir=output_dir,
                    crc_correction=options.get("crc_correction", True),
                    asset_types=options.get("asset_types", ["Texture2D", "TextAsset", "Mesh"]),
                    strategy=options.get("strategy", "path_id"),
                    compression=options.get("compression", "lzma")
                )

                by_name = {t.original_name: t for t in targets}
                for out_path in output_paths:
                    target = by_name.get(out_path.name)
                    file_service.create_output_file(
                        session_uuid=session_uuid,
                        file_path=out_path,
                        original_name=target.original_name if target else out_path.name,
                        task_id=task_id
                    )

                if not output_paths:
                    task_service.update_status(
                        task_id, TaskStatus.COMPLETED,
                        "All target files are already up to date; nothing to update.",
                        cli_log=cli_log
                    )
                else:
                    task_service.update_status(task_id, TaskStatus.COMPLETED, cli_log=cli_log)

            except RuntimeError as e:
                err_log = ""
                if hasattr(e, 'args') and len(e.args) > 1:
                    err_log = e.args[1] if isinstance(e.args[1], str) else str(e.args[1])
                task_service.update_status(task_id, TaskStatus.FAILED, str(e.args[0]) if e.args else str(e), cli_log=err_log)
            finally:
                if link_root.exists():
                    shutil.rmtree(link_root, ignore_errors=True)

        finally:
            db.close()


async def execute_pack_task(task_id: str, session_uuid: str, options: dict):
    """Execute a pack task in the background with concurrency control.

    The same asset folder is packed into every target bundle — one Spine animation may be
    split across two bundles. Accepts both the batch list (target_bundle_file_ids) and the
    legacy single id (target_bundle_file_id).
    """
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

            target_ids = options.get("target_bundle_file_ids") or (
                [options["target_bundle_file_id"]] if options.get("target_bundle_file_id") else []
            )
            targets = [f for f in (file_service.get(fid) for fid in target_ids) if f]

            if not targets:
                task_service.update_status(task_id, TaskStatus.FAILED, "Target bundle(s) not found")
                return

            # Each target becomes an output named after it, so duplicate names would collide.
            target_names = [t.original_name for t in targets]
            if len(set(target_names)) != len(target_names):
                task_service.update_status(
                    task_id, TaskStatus.FAILED,
                    "Duplicate target filenames are not supported; upload each target bundle only once."
                )
                return

            # Create asset folder from uploaded files
            asset_folder = settings.temp_path / session_uuid / task_id / "assets"
            asset_folder.mkdir(parents=True, exist_ok=True)

            # Copy uploaded asset files to temp folder
            asset_file_ids = options.get("asset_folder_files", [])
            for file_id in asset_file_ids:
                asset_file = file_service.get(file_id)
                if asset_file:
                    shutil.copy(asset_file.stored_path, asset_folder / asset_file.original_name)

            # Create output directory
            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)

            # Named links let the kernel read the target CRC from the output filename. Each
            # target gets its own subdir so same-named links can never clobber each other.
            link_root = output_dir / "_links"
            target_links = [
                _create_named_link(Path(t.stored_path), t.original_name, link_root / str(i))
                for i, t in enumerate(targets)
            ]

            try:
                output_paths, cli_log = await cli_runner.run_pack(
                    asset_folder=asset_folder,
                    target_bundles=target_links,
                    output_dir=output_dir,
                    crc_correction=options.get("crc_correction", True),
                    compression=options.get("compression", "lzma")
                )

                by_name = {t.original_name: t for t in targets}
                for out_path in output_paths:
                    target = by_name.get(out_path.name)
                    file_service.create_output_file(
                        session_uuid=session_uuid,
                        file_path=out_path,
                        original_name=target.original_name if target else out_path.name,
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
                if link_root.exists():
                    shutil.rmtree(link_root, ignore_errors=True)

        finally:
            db.close()

async def execute_extract_task(task_id: str, session_uuid: str, options: dict):
    """Execute extract task in background with concurrency control.
    
    When multiple bundles are uploaded, extracts each bundle separately into
    a character-named subdirectory, then creates one ZIP per character group.
    """
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
            
            # Get bundle files with their metadata
            bundle_file_ids = options.get("bundle_file_ids", [])
            bundle_files = []
            for file_id in bundle_file_ids:
                bundle_file = file_service.get(file_id)
                if bundle_file:
                    bundle_files.append(bundle_file)
            
            if not bundle_files:
                task_service.update_status(task_id, TaskStatus.FAILED, "No bundle files found")
                return
            
            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                import zipfile
                
                if len(bundle_files) == 1:
                    # Single bundle: extract directly, one ZIP
                    bundle_file = bundle_files[0]
                    
                    # Create named link for proper subdir naming
                    link_dir = output_dir / "_links"
                    bundle_link = _create_named_link(
                        Path(bundle_file.stored_path), bundle_file.original_name, link_dir
                    )
                    
                    result_dir, cli_log = await cli_runner.run_extract(
                        bundle_paths=[bundle_link],
                        output_dir=output_dir,
                        asset_types=options.get("asset_types", ["Texture2D", "TextAsset", "Mesh"]),
                        unpack_atlas=options.get("unpack_atlas", False)
                    )
                    
                    # Cleanup named links
                    if link_dir.exists():
                        shutil.rmtree(link_dir, ignore_errors=True)
                    
                    # Find the actual output directory (CLI may create a subdir)
                    # When single bundle, CLI auto-creates subdir from filename core
                    actual_output = result_dir
                    subdirs = [d for d in result_dir.iterdir() if d.is_dir()]
                    if len(subdirs) == 1 and not list(result_dir.glob("*.*")):
                        actual_output = subdirs[0]
                    
                    # Create ZIP
                    zip_name = Path(bundle_file.original_name).stem + "_extracted.zip"
                    zip_path = output_dir / zip_name
                    
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for extracted_file in actual_output.rglob("*"):
                            if extracted_file.is_file():
                                rel_path = extracted_file.relative_to(actual_output)
                                zipf.write(extracted_file, rel_path)
                    
                    file_service.create_output_file(
                        session_uuid=session_uuid,
                        file_path=zip_path,
                        original_name=zip_name,
                        task_id=task_id
                    )
                    
                else:
                    # Multiple bundles: extract each separately, group by character
                    # Parse character name from each bundle's original filename
                    character_bundles = {}  # character_name -> [bundle_files]
                    
                    for bundle_file in bundle_files:
                        # Extract character name from original filename
                        # e.g., "assets-_mx-spinelobbies-yuuka_home-_mxdependency-2024-11-18_002_assets_all_793614109.bundle"
                        # -> core = "spinelobbies-yuuka_home" -> character = "yuuka_home"
                        char_name = _extract_character_from_filename(bundle_file.original_name)
                        if char_name not in character_bundles:
                            character_bundles[char_name] = []
                        character_bundles[char_name].append(bundle_file)
                    
                    all_logs = []
                    
                    # Extract each character group separately
                    for char_name, char_bundle_files in character_bundles.items():
                        char_output_dir = output_dir / char_name
                        char_output_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Create named links for this character's bundles
                        link_dir = char_output_dir / "_links"
                        bundle_links = []
                        for bf in char_bundle_files:
                            bundle_links.append(_create_named_link(
                                Path(bf.stored_path), bf.original_name, link_dir
                            ))
                        
                        # Extract with subdir = character name
                        result_dir, char_log = await cli_runner.run_extract(
                            bundle_paths=bundle_links,
                            output_dir=char_output_dir,
                            asset_types=options.get("asset_types", ["Texture2D", "TextAsset", "Mesh"]),
                            unpack_atlas=options.get("unpack_atlas", False),
                            subdir=char_name
                        )
                        
                        all_logs.append(char_log)
                        
                        # Cleanup named links
                        if link_dir.exists():
                            shutil.rmtree(link_dir, ignore_errors=True)
                        
                        # Find actual output directory
                        actual_output = char_output_dir / char_name
                        if not actual_output.exists():
                            actual_output = char_output_dir
                        
                        # Create per-character ZIP
                        zip_name = f"{char_name}_extracted.zip"
                        zip_path = output_dir / zip_name
                        
                        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for extracted_file in actual_output.rglob("*"):
                                if extracted_file.is_file():
                                    rel_path = extracted_file.relative_to(actual_output)
                                    zipf.write(extracted_file, rel_path)
                        
                        file_service.create_output_file(
                            session_uuid=session_uuid,
                            file_path=zip_path,
                            original_name=zip_name,
                            task_id=task_id
                        )
                    
                    cli_log = "\n\n".join(all_logs)
                
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
    """Execute a CRC task in the background with concurrency control.

    Fix mode copies the uploaded file and fixes the copy's CRC in place, leaving the stored
    upload untouched. Check mode compares against a reference file if given (else against
    the CRC in the filename) and modifies nothing.
    """
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
            reference_id = options.get("reference_file_id")
            target_crc = options.get("target_crc")
            check = options.get("check", False)

            modified_file = file_service.get(modified_id)
            if not modified_file:
                task_service.update_status(task_id, TaskStatus.FAILED, "Modified bundle file not found")
                return

            reference_file = file_service.get(reference_id) if reference_id else None

            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            link_dir = output_dir / "_links"
            link_dir.mkdir(parents=True, exist_ok=True)

            # The kernel reads the target CRC from the file's name, so work on a file named
            # with the original filename. Fix mode rewrites in place, so use a real copy to
            # avoid mutating the stored upload; check mode never writes, so a link is fine.
            if check:
                modified_path = _create_named_link(
                    Path(modified_file.stored_path), modified_file.original_name, link_dir
                )
            else:
                modified_path = link_dir / modified_file.original_name
                shutil.copy2(str(modified_file.stored_path), str(modified_path))

            try:
                output_path, cli_log = await cli_runner.run_crc(
                    modified_path=modified_path,
                    reference_path=Path(reference_file.stored_path) if reference_file else None,
                    target_crc=target_crc,
                    check=check,
                    no_backup=True
                )

                if check:
                    # Check mode modifies nothing, it just reports the comparison.
                    task_service.update_status(task_id, TaskStatus.COMPLETED, cli_log=cli_log)
                    return

                # Register the fixed copy as the task's output.
                file_service.create_output_file(
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
                # Cleanup working copies/links
                if link_dir.exists():
                    shutil.rmtree(link_dir, ignore_errors=True)

        finally:
            db.close()


@router.post("/update", response_model=TaskResponse)
def create_update_task(
    request: UpdateTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a mod update task. One pooled N-to-N run: every old mod's assets are applied to every target."""
    session_service = SessionService(db)
    session = session_service.get(request.session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get file info to extract character name
    file_service = FileService(db)
    
    if request.is_batch():
        # Batch mode: extract character names from all files
        char_names = set()
        for fid in request.old_bundle_file_ids + request.target_file_ids:
            f = file_service.get(fid)
            if f:
                cn = extract_character_name(f.original_name)
                if cn != "unknown":
                    char_names.add(cn)
        
        if char_names:
            if len(char_names) == 1:
                name = char_names.pop()
            else:
                first = sorted(char_names)[0]
                name = f"{first}/... ({len(char_names)})"
        else:
            name = f"{len(request.old_bundle_file_ids)} items"
    else:
        # Single mode
        old_bundle_file = file_service.get(request.old_bundle_file_id) if request.old_bundle_file_id else None
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
    target_ids = request.target_bundle_file_ids or (
        [request.target_bundle_file_id] if request.target_bundle_file_id else []
    )
    char_names = set()
    for fid in target_ids:
        f = file_service.get(fid)
        if f:
            cn = extract_character_name(f.original_name)
            if cn != "unknown":
                char_names.add(cn)
    if not char_names:
        name = f"{len(target_ids)} items" if target_ids else "unknown"
    elif len(char_names) == 1:
        name = char_names.pop()
    else:
        first = sorted(char_names)[0]
        name = f"{first}/... ({len(char_names)})"
    
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
    
    # Get file info to extract character names from all bundles
    file_service = FileService(db)
    name = "unknown"
    if request.bundle_file_ids:
        char_names = set()
        for fid in request.bundle_file_ids:
            bf = file_service.get(fid)
            if bf:
                cn = extract_character_name(bf.original_name)
                if cn != "unknown":
                    char_names.add(cn)
        if char_names:
            if len(char_names) == 1:
                name = char_names.pop()
            else:
                first = sorted(char_names)[0]
                name = f"{first}/... ({len(char_names)})"
        else:
            name = f"{len(request.bundle_file_ids)} items"
    
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
    
    Fix mode repairs the CRC in place; check mode compares against an optional reference file.
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