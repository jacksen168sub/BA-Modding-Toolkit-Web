import asyncio
import subprocess
import shutil
import os
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

from ..config import settings
from ..models.task import Task, TaskType, TaskStatus


class CLIRunner:
    """Execute BA-Modding-Toolkit CLI commands."""
    
    def __init__(self):
        self.upstream_dir = self._find_upstream_dir()
        self.timeout = settings.CLI_TIMEOUT
    
    def _find_upstream_dir(self) -> Path:
        """Find the upstream BA-Modding-Toolkit directory."""
        upstream_dir = settings.PROJECT_ROOT / "upstream" / "BA-Modding-Toolkit"
        if upstream_dir.exists():
            return upstream_dir
        raise FileNotFoundError(f"BA-Modding-Toolkit not found at {upstream_dir}")
    
    def _run_command_sync(
        self,
        args: List[str],
        cwd: Optional[Path] = None
    ) -> Tuple[int, str, str]:
        """
        Run CLI command synchronously using `uv run bamt-cli`.
        This is a blocking call, should only be used with asyncio.to_thread.
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = ["uv", "run", "bamt-cli"] + args
        
        # 添加环境变量确保日志实时输出和正确编码
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["BAMT_LANG"] = "en-US"  # Force CLI to use English for logs
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=self.timeout,
            cwd=cwd or self.upstream_dir,
            env=env
        )
        
        return result.returncode, result.stdout, result.stderr

    async def _run_command(
        self,
        args: List[str],
        cwd: Optional[Path] = None
    ) -> Tuple[int, str, str]:
        """
        Run CLI command asynchronously by offloading to thread pool.
        This prevents blocking the event loop.
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        return await asyncio.to_thread(self._run_command_sync, args, cwd)
    
    def _build_log(self, cmd: List[str], stdout: str, stderr: str, returncode: int) -> str:
        """Build formatted log string."""
        log_parts = [
            f"=== CLI Command ===",
            f"Command: {' '.join(cmd)}",
            f"Working Directory: {self.upstream_dir}",
            f"Return Code: {returncode}",
            f"",
            f"=== STDOUT ===",
            stdout if stdout else "(empty)",
            f"",
            f"=== STDERR ===",
            stderr if stderr else "(empty)",
        ]
        return "\n".join(log_parts)
    
    async def run_command_async(
        self,
        args: List[str],
        cwd: Optional[Path] = None
    ) -> Tuple[int, str, str]:
        """
        Run CLI command asynchronously using `uv run bamt-cli`.
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = ["uv", "run", "bamt-cli"] + args
        
        # 添加环境变量确保日志实时输出
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["BAMT_LANG"] = "en-US"  # Force CLI to use English for logs
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd or self.upstream_dir),
            env=env
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )
            return process.returncode, stdout.decode(), stderr.decode()
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(f"CLI command timed out after {self.timeout} seconds")
    
    async def run_update(
        self,
        old_bundle: Path,
        output_dir: Path,
        target_bundle: Optional[Path] = None,
        resource_dir: Optional[Path] = None,
        crc_correction: bool = True,
        asset_types: List[str] = None
    ) -> Tuple[Path, str]:
        """
        Run mod update command asynchronously.
        
        Args:
            old_bundle: Path to the old Mod bundle file
            output_dir: Directory to save output
            target_bundle: Path to the new game resource bundle (optional)
            resource_dir: Path to game resource directory (optional)
            crc_correction: Whether to apply CRC fix
            asset_types: List of asset types to replace
        
        Returns:
            Tuple of (output_path, full_log)
        """
        args = [
            "update",
            str(old_bundle),
            "--output-dir", str(output_dir)
        ]
        
        if target_bundle:
            args.extend(["--target", str(target_bundle)])
        
        if resource_dir:
            args.extend(["--resource-dir", str(resource_dir)])
        
        if not crc_correction:
            args.append("--no-crc")
        
        if asset_types:
            args.extend(["--asset-types"] + asset_types)
        
        # Add compression parameter from config
        args.extend(["--compression", settings.CLI_COMPRESSION])
        
        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)
        
        # Build full log
        full_log = self._build_log(cmd, stdout, stderr, returncode)
        
        if returncode != 0:
            raise RuntimeError(f"Update failed: {stderr or stdout}", full_log)
        
        output_files = list(output_dir.glob("*.bundle"))
        if output_files:
            return output_files[0], full_log
        
        raise FileNotFoundError("No output bundle generated", full_log)
    
    async def run_pack(
        self,
        asset_folder: Path,
        target_bundle: Path,
        output_dir: Path,
        crc_correction: bool = True
    ) -> Tuple[Path, str]:
        """
        Run asset pack command asynchronously.
        
        Returns:
            Tuple of (output_path, full_log)
        """
        args = [
            "pack",
            "--bundle", str(target_bundle),
            "--folder", str(asset_folder),
            "--output-dir", str(output_dir)
        ]
        
        if not crc_correction:
            args.append("--no-crc")
        
        # Add compression parameter from config
        args.extend(["--compression", settings.CLI_COMPRESSION])
        
        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)
        
        full_log = self._build_log(cmd, stdout, stderr, returncode)
        
        if returncode != 0:
            raise RuntimeError(f"Pack failed: {stderr or stdout}", full_log)
        
        output_files = list(output_dir.glob("*.bundle"))
        if output_files:
            return output_files[0], full_log
        
        raise FileNotFoundError("No output bundle generated", full_log)
    
    async def run_extract(
        self,
        bundle_paths: List[Path],
        output_dir: Path,
        asset_types: List[str] = None
    ) -> Tuple[Path, str]:
        """
        Run asset extract command asynchronously.
        
        Returns:
            Tuple of (output_dir, full_log)
        """
        args = [
            "extract"
        ] + [str(p) for p in bundle_paths] + [
            "--output-dir", str(output_dir)
        ]
        
        if asset_types:
            args.extend(["--asset-types"] + asset_types)
        
        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)
        
        full_log = self._build_log(cmd, stdout, stderr, returncode)
        
        if returncode != 0:
            raise RuntimeError(f"Extract failed: {stderr or stdout}", full_log)
        
        return output_dir, full_log
    
    async def run_crc(
        self,
        modified_path: Path,
        original_path: Path,
        no_backup: bool = False
    ) -> Tuple[Path, str]:
        """
        Run CRC correction command asynchronously.
        
        Args:
            modified_path: Path to the modified file (to be fixed)
            original_path: Path to the original file (provides target CRC value)
            no_backup: Do not create a backup (.bak) before fixing the file
        
        Returns:
            Tuple of (output_path, full_log)
        
        Note:
            The CLI modifies the file in-place. If no_backup is False,
            a .bak backup is created. The output_path points to the modified file.
        """
        # Note: 'modified' is a positional argument, not --modified
        args = [
            "crc",
            str(modified_path),
            "--original", str(original_path)
        ]
        
        if no_backup:
            args.append("--no-backup")
        
        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)
        
        full_log = self._build_log(cmd, stdout, stderr, returncode)
        
        if returncode != 0:
            raise RuntimeError(f"CRC correction failed: {stderr or stdout}", full_log)
        
        # CRC modifies the file in-place, return the modified file path
        return modified_path, full_log


# Global CLI runner instance
cli_runner = CLIRunner()
