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
    """Extract character identifier from a BA bundle filename.
    
    Parses the bundle filename using the same logic as the upstream naming module
    to extract the character name (core field).
    
    Examples:
        "assets-_mx-spinelobbies-yuuka_home-_mxdependency-2024-11-18_002_assets_all_793614109.bundle"
        -> "yuuka_home"
        
        "assets-_mx-spinecharacters-ch0808_spr-_mxprolog-2024-11-18_textures_12345678.bundle"
        -> "ch0808_spr"
    
    Falls back to the stem of the filename if parsing fails.
    """
    import re
    
    # Remove extension
    name = filename.rsplit('.', 1)[0]
    
    # Try to extract core part using the same logic as upstream naming.py
    # Pattern: after "assets-_mx-{category}-" and before "-_mxdependency" or "-_mxprolog" or "-_mxload"
    match = re.search(
        r'assets-_mx-(?:spinelobbies|spinebackground|spinecharacters|characters)-(.+?)-(?:_mxdependency|_mxprolog|_mxload)',
        name,
        re.IGNORECASE
    )
    if match:
        return match.group(1)
    
    # Fallback: try simpler pattern - just the part between category prefix and mx marker
    match = re.search(r'-([a-zA-Z0-9_]+)-_mx', name)
    if match:
        return match.group(1)
    
    # Final fallback: use the stem
    return name


from ..models.database import get_db
from ..models.task import TaskType, TaskStatus
from ..models.schemas import (
    TaskResponse, TaskBrief, TaskCreate, QueueInfo,
    UpdateTaskCreate, PackTaskCreate, ExtractTaskCreate, CrcTaskCreate,
    SplitTaskCreate, MergeTaskCreate,
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


def _extract_bundle_sort_key(filename: str) -> str:
    """Extract a sort key from a bundle filename for matching old mods to targets.
    
    Strips the trailing CRC number so bundles from different versions
    (with different CRCs) can be matched by their identity.
    
    Example:
        "assets-_mx-spinelobbies-yuuka_home-_mxdependency-2024-11-18_002_assets_all_793614109.bundle"
        -> "assets-_mx-spinelobbies-yuuka_home-_mxdependency-2024-11-18_002_assets_all"
    """
    import re
    name = filename.rsplit('.', 1)[0]  # Remove extension
    # Remove trailing _DIGITS (CRC) — the last occurrence of _ followed by only digits
    match = re.match(r'^(.+)_(\d+)$', name)
    if match:
        return match.group(1)
    return name


async def execute_update_task(task_id: str, session_uuid: str, options: dict):
    """Execute update task in background with concurrency control.
    
    Supports both single and batch modes:
    - Single: old_bundle_file_id + target_file_id
    - Batch: old_bundle_file_ids + target_file_ids, auto-matched by character name
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
            
            # Determine single vs batch mode
            old_bundle_ids = options.get("old_bundle_file_ids", [])
            target_ids = options.get("target_file_ids", [])
            
            if old_bundle_ids and target_ids:
                # Batch mode
                pairs = _match_update_pairs(old_bundle_ids, target_ids, file_service)
                if not pairs:
                    task_service.update_status(
                        task_id, TaskStatus.FAILED,
                        "No matching old mod / target pairs found. "
                        "Ensure files share the same character name."
                    )
                    return
            else:
                # Single mode (backward compatible)
                old_bundle_id = options.get("old_bundle_file_id")
                target_id = options.get("target_file_id")
                
                old_bundle_file = file_service.get(old_bundle_id) if old_bundle_id else None
                target_file = file_service.get(target_id) if target_id else None
                
                if not old_bundle_file:
                    task_service.update_status(task_id, TaskStatus.FAILED, "Old mod file not found")
                    return
                if not target_file:
                    task_service.update_status(
                        task_id, TaskStatus.FAILED,
                        "Target game file not found. Please upload the new game resource bundle."
                    )
                    return
                
                pairs = [(old_bundle_file, target_file)]
            
            # Create output directory
            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            all_logs = []
            success_count = 0
            
            try:
                for idx, (old_bundle_file, target_file) in enumerate(pairs):
                    # Create named links for CRC correction support
                    link_dir = output_dir / f"_links_{idx}"
                    target_link = _create_named_link(
                        Path(target_file.stored_path), target_file.original_name, link_dir
                    )
                    
                    try:
                        output_path, pair_log = await cli_runner.run_update(
                            old_bundle=Path(old_bundle_file.stored_path),
                            output_dir=output_dir,
                            target_bundle=target_link,
                            crc_correction=options.get("crc_correction", True),
                            asset_types=options.get("asset_types", ["Texture2D", "TextAsset", "Mesh"]),
                            strategy=options.get("strategy", "path_id"),
                            compression=options.get("compression", "lzma")
                        )
                        
                        # Create output file record
                        file_service.create_output_file(
                            session_uuid=session_uuid,
                            file_path=output_path,
                            original_name=target_file.original_name,
                            task_id=task_id
                        )
                        
                        all_logs.append(f"--- Pair {idx+1}: {old_bundle_file.original_name} -> {target_file.original_name} ---\n{pair_log}")
                        success_count += 1
                        
                    except RuntimeError as e:
                        err_log = ""
                        if hasattr(e, 'args') and len(e.args) > 1:
                            err_log = e.args[1] if isinstance(e.args[1], str) else str(e.args[1])
                        all_logs.append(f"--- Pair {idx+1}: {old_bundle_file.original_name} -> {target_file.original_name} FAILED ---\n{err_log or str(e)}")
                    finally:
                        if link_dir.exists():
                            shutil.rmtree(link_dir, ignore_errors=True)
                
                cli_log = "\n\n".join(all_logs)
                
                if success_count == 0:
                    task_service.update_status(task_id, TaskStatus.FAILED, "All update pairs failed", cli_log=cli_log)
                elif success_count < len(pairs):
                    task_service.update_status(
                        task_id, TaskStatus.COMPLETED,
                        f"Partially completed: {success_count}/{len(pairs)} pairs succeeded",
                        cli_log=cli_log
                    )
                else:
                    task_service.update_status(task_id, TaskStatus.COMPLETED, cli_log=cli_log)
                    
            except Exception as e:
                task_service.update_status(task_id, TaskStatus.FAILED, str(e), cli_log="\n\n".join(all_logs))
                
        finally:
            db.close()


def _match_update_pairs(old_bundle_ids: list, target_ids: list, file_service) -> list:
    """Match old mod files to target files by character name for batch update.
    
    Matching strategy:
    1. Group old mods and targets by character name (extracted from filename)
    2. Within each character group, sort both lists by filename and match 1:1
    3. Return list of (old_bundle_file, target_file) tuples
    
    Returns empty list if no matches found.
    """
    # Load files and group by character name
    old_by_char = {}  # char_name -> [(sort_key, file_record)]
    for fid in old_bundle_ids:
        f = file_service.get(fid)
        if f:
            char = _extract_character_from_filename(f.original_name)
            sort_key = _extract_bundle_sort_key(f.original_name)
            old_by_char.setdefault(char, []).append((sort_key, f))
    
    target_by_char = {}
    for fid in target_ids:
        f = file_service.get(fid)
        if f:
            char = _extract_character_from_filename(f.original_name)
            sort_key = _extract_bundle_sort_key(f.original_name)
            target_by_char.setdefault(char, []).append((sort_key, f))
    
    pairs = []
    for char_name in sorted(set(old_by_char.keys()) & set(target_by_char.keys())):
        old_list = sorted(old_by_char[char_name], key=lambda x: x[0])
        target_list = sorted(target_by_char[char_name], key=lambda x: x[0])
        
        # Match 1:1 by sorted position
        for (_, old_file), (_, target_file) in zip(old_list, target_list):
            pairs.append((old_file, target_file))
    
    return pairs


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
            
            # Create named link for CRC correction support
            link_dir = output_dir / "_links"
            target_link = _create_named_link(
                Path(target_file.stored_path), target_file.original_name, link_dir
            )
            
            try:
                output_path, cli_log = await cli_runner.run_pack(
                    asset_folder=asset_folder,
                    target_bundle=target_link,
                    output_dir=output_dir,
                    crc_correction=options.get("crc_correction", True),
                    compression=options.get("compression", "lzma")
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
                # Cleanup named links
                if link_dir.exists():
                    shutil.rmtree(link_dir, ignore_errors=True)
                
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
            
            # Create named links for CRC correction support
            # The CLI crc command extracts target CRC from the modified file's name
            output_dir = settings.output_path / session_uuid / task_id
            link_dir = output_dir / "_links"
            modified_link = _create_named_link(
                Path(modified_file.stored_path), modified_file.original_name, link_dir
            )
            
            try:
                check_only = options.get("check_only", False)
                output_path, cli_log = await cli_runner.run_crc(
                    modified_path=modified_link,
                    original_path=Path(original_file.stored_path),
                    no_backup=True,
                    check_only=check_only
                )
                
                if check_only:
                    # check_only mode does not modify files, just report CRC comparison
                    task_service.update_status(task_id, TaskStatus.COMPLETED, cli_log=cli_log)
                    return
                
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
                # Cleanup named links
                if link_dir.exists():
                    shutil.rmtree(link_dir, ignore_errors=True)
                
        finally:
            db.close()


async def execute_split_task(task_id: str, session_uuid: str, options: dict):
    """Execute split task in background: legacy bundle -> multiple modern bundles (one-to-many)."""
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
            
            # Get legacy bundle file
            legacy_file_id = options.get("legacy_file_id")
            legacy_file = file_service.get(legacy_file_id)
            if not legacy_file:
                task_service.update_status(task_id, TaskStatus.FAILED, "Legacy bundle file not found")
                return
            
            # Get modern bundle file list
            modern_file_ids = options.get("modern_file_ids", [])
            modern_paths = []
            modern_files = []
            for fid in modern_file_ids:
                f = file_service.get(fid)
                if f:
                    modern_files.append(f)
            
            if not modern_files:
                task_service.update_status(task_id, TaskStatus.FAILED, "No modern bundle files provided")
                return
            
            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create named links for CRC correction support
            link_dir = output_dir / "_links"
            legacy_link = _create_named_link(
                Path(legacy_file.stored_path), legacy_file.original_name, link_dir
            )
            modern_links = []
            for f in modern_files:
                modern_links.append(_create_named_link(
                    Path(f.stored_path), f.original_name, link_dir
                ))
            
            try:
                output_files, cli_log = await cli_runner.run_split(
                    legacy_bundle=legacy_link,
                    modern_bundles=modern_links,
                    output_dir=output_dir,
                    crc_correction=options.get("crc_correction", True),
                    asset_types=options.get("asset_types", ["Texture2D", "TextAsset", "Mesh"]),
                    compression=options.get("compression", "lzma")
                )
                
                # Create output file record for each output
                for output_path in output_files:
                    file_service.create_output_file(
                        session_uuid=session_uuid,
                        file_path=output_path,
                        original_name=output_path.name,
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
                # Cleanup named links
                if link_dir.exists():
                    shutil.rmtree(link_dir, ignore_errors=True)
                
        finally:
            db.close()


async def execute_merge_task(task_id: str, session_uuid: str, options: dict):
    """Execute merge task in background: multiple modern bundles -> legacy bundle (many-to-one)."""
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
            
            # Get legacy bundle file
            legacy_file_id = options.get("legacy_file_id")
            legacy_file = file_service.get(legacy_file_id)
            if not legacy_file:
                task_service.update_status(task_id, TaskStatus.FAILED, "Legacy bundle file not found")
                return
            
            # Get modern bundle file list
            modern_file_ids = options.get("modern_file_ids", [])
            modern_paths = []
            modern_files = []
            for fid in modern_file_ids:
                f = file_service.get(fid)
                if f:
                    modern_files.append(f)
            
            if not modern_files:
                task_service.update_status(task_id, TaskStatus.FAILED, "No modern bundle files provided")
                return
            
            output_dir = settings.output_path / session_uuid / task_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create named links for CRC correction support
            link_dir = output_dir / "_links"
            legacy_link = _create_named_link(
                Path(legacy_file.stored_path), legacy_file.original_name, link_dir
            )
            modern_links = []
            for f in modern_files:
                modern_links.append(_create_named_link(
                    Path(f.stored_path), f.original_name, link_dir
                ))
            
            try:
                output_path, cli_log = await cli_runner.run_merge(
                    legacy_bundle=legacy_link,
                    modern_bundles=modern_links,
                    output_dir=output_dir,
                    crc_correction=options.get("crc_correction", True),
                    asset_types=options.get("asset_types", ["Texture2D", "TextAsset", "Mesh"]),
                    compression=options.get("compression", "lzma")
                )
                
                file_service.create_output_file(
                    session_uuid=session_uuid,
                    file_path=output_path,
                    original_name=legacy_file.original_name,
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
                # Cleanup named links
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
    """Create a mod update task. Supports both single and batch modes."""
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


@router.post("/split", response_model=TaskResponse)
def create_split_task(
    request: SplitTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a split task: distribute legacy bundle assets to multiple modern bundles (one-to-many)."""
    session_service = SessionService(db)
    session = session_service.get(request.session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    file_service = FileService(db)
    legacy_file = file_service.get(request.legacy_file_id)
    name = extract_character_name(legacy_file.original_name) if legacy_file else "unknown"
    
    task_service = TaskService(db)
    task = task_service.create(
        session_uuid=request.session_uuid,
        task_type=TaskType.SPLIT,
        options=request.model_dump(),
        name=name
    )
    
    background_tasks.add_task(
        execute_split_task,
        task.id,
        request.session_uuid,
        request.model_dump()
    )
    
    return get_task_response(task, db)


@router.post("/merge", response_model=TaskResponse)
def create_merge_task(
    request: MergeTaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a merge task: merge multiple modern bundle assets into a legacy bundle (many-to-one)."""
    session_service = SessionService(db)
    session = session_service.get(request.session_uuid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    file_service = FileService(db)
    legacy_file = file_service.get(request.legacy_file_id)
    name = extract_character_name(legacy_file.original_name) if legacy_file else "unknown"
    
    task_service = TaskService(db)
    task = task_service.create(
        session_uuid=request.session_uuid,
        task_type=TaskType.MERGE,
        options=request.model_dump(),
        name=name
    )
    
    background_tasks.add_task(
        execute_merge_task,
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