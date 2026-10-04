import asyncio
import subprocess
import shutil
import os
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

from ..config import settings


class CLIRunner:
    """Execute BA-Modding-Toolkit CLI commands."""
    
    def __init__(self):
        self.upstream_dir = self._find_upstream_dir()
        self.timeout = settings.CLI_TIMEOUT
    
    # Patterns indicating CLI soft failures (exit code 0 but operation didn't produce expected output).
    # Note: "all_targets_unchanged" is deliberately absent — under the kernel's N-to-N update it is a
    # success signal (the targets matched but needed no change), not a failure.
    _SOFT_FAILURE_PATTERNS = [
        "CRC Correction failed",
        "Operation Failed",
    ]
    
    def _check_soft_failure(self, stdout: str) -> str | None:
        """Check CLI stdout for soft failure patterns (exit code 0 but operation failed).
        
        Returns the first matching error description, or None if no soft failure detected.
        """
        for pattern in self._SOFT_FAILURE_PATTERNS:
            if pattern in stdout:
                # Extract the line containing the error for context
                for line in stdout.splitlines():
                    if pattern in line:
                        return line.strip()
                return pattern
        return None
    
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
        source_files: List[Path],
        target_files: List[Path],
        output_dir: Path,
        resource_dir: Optional[Path] = None,
        crc_correction: bool = True,
        asset_types: List[str] = None,
        strategy: str = "path_id",
        compression: str = "lzma"
    ) -> Tuple[List[Path], str]:
        """
        Run a N-to-N mod update asynchronously.

        Every source file's assets are pooled by the kernel and applied to every target;
        each changed target yields one output bundle named after that target's filename.

        Args:
            source_files: Paths to the old Mod bundle files (the asset pool)
            target_files: Paths to the new game resource bundles (each receives the pool)
            output_dir: Directory to save outputs
            resource_dir: Path to game resource directory (alternative to explicit targets)
            crc_correction: Whether to apply CRC fix
            asset_types: List of asset types to replace
            strategy: Match strategy (path_id, cont_name_type, name_type)
            compression: Compression method (lzma, lz4, original, none)

        Returns:
            Tuple of (output paths, full_log). The list is empty when every target was
            already up to date (kernel reports "all_targets_unchanged" — a success).
        """
        args = [
            "update",
            *[str(p) for p in source_files],
            "--output-dir", str(output_dir),
        ]

        if target_files:
            args.extend(["--target"] + [str(p) for p in target_files])

        if resource_dir:
            args.extend(["--resource-dir", str(resource_dir)])

        if not crc_correction:
            args.append("--no-crc")

        if asset_types:
            args.extend(["--asset-types"] + asset_types)

        args.extend(["--strategy", strategy])
        args.extend(["--compression", compression])

        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)

        # Build full log
        full_log = self._build_log(cmd, stdout, stderr, returncode)

        if returncode != 0:
            raise RuntimeError(f"Update failed: {stderr or stdout}", full_log)

        output_files = sorted(output_dir.glob("*.bundle"))
        if output_files:
            return output_files, full_log

        # No output file — check for soft failure patterns in stdout
        soft_error = self._check_soft_failure(stdout)
        if soft_error:
            if "CRC Correction failed" in soft_error:
                raise RuntimeError(
                    "Update failed: CRC correction failed. Try disabling CRC correction or using a different compression method.",
                    full_log
                )
            raise RuntimeError(f"Update failed: {soft_error}", full_log)

        # Nothing changed: the kernel reports "all_targets_unchanged" as a success.
        if "all_targets_unchanged" in stdout:
            return [], full_log

        raise FileNotFoundError("No output bundle generated", full_log)
    
    async def run_pack(
        self,
        asset_folder: Path,
        target_bundles: List[Path],
        output_dir: Path,
        crc_correction: bool = True,
        compression: str = "lzma"
    ) -> Tuple[List[Path], str]:
        """
        Run the asset pack command asynchronously.

        The same asset folder is packed into every target bundle; each changed target
        yields one output bundle named after that target's filename.

        Args:
            asset_folder: Folder holding the assets to inject
            target_bundles: Target bundle files (each receives the assets)
            output_dir: Directory to save outputs
            crc_correction: Whether to apply CRC fix
            compression: Compression method (lzma, lz4, original, none)

        Returns:
            Tuple of (output paths, full_log). The CLI reports "Operation Failed" when no
            assets matched, which surfaces as a RuntimeError rather than an empty list.
        """
        args = [
            "pack",
            "--bundle", *[str(b) for b in target_bundles],
            "--folder", str(asset_folder),
            "--output-dir", str(output_dir),
        ]

        if not crc_correction:
            args.append("--no-crc")

        args.extend(["--compression", compression])

        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)

        full_log = self._build_log(cmd, stdout, stderr, returncode)

        if returncode != 0:
            raise RuntimeError(f"Pack failed: {stderr or stdout}", full_log)

        output_files = sorted(output_dir.glob("*.bundle"))
        if output_files:
            return output_files, full_log

        # No output file — check for soft failure patterns in stdout
        soft_error = self._check_soft_failure(stdout)
        if soft_error:
            if "CRC Correction failed" in soft_error:
                raise RuntimeError(
                    "Pack failed: CRC correction failed. Try disabling CRC correction or using a different compression method.",
                    full_log
                )
            raise RuntimeError(f"Pack failed: {soft_error}", full_log)

        raise FileNotFoundError("No output bundle generated", full_log)

    async def run_extract(
        self,
        bundle_paths: List[Path],
        output_dir: Path,
        asset_types: List[str] = None,
        unpack_atlas: bool = False,
        subdir: str = None
    ) -> Tuple[Path, str]:
        """
        Run asset extract command asynchronously.
        
        Args:
            unpack_atlas: Unpack Atlas into individual PNG frames
            subdir: Subdirectory name within output_dir
        
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
        
        if unpack_atlas:
            args.append("--unpack-atlas")
        
        if subdir:
            args.extend(["--subdir", subdir])
        
        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)
        
        full_log = self._build_log(cmd, stdout, stderr, returncode)
        
        if returncode != 0:
            raise RuntimeError(f"Extract failed: {stderr or stdout}", full_log)
        
        return output_dir, full_log
    
    async def run_crc(
        self,
        modified_path: Path,
        reference_path: Optional[Path] = None,
        target_crc: Optional[str] = None,
        check: bool = False,
        no_backup: bool = True
    ) -> Tuple[Optional[Path], str]:
        """
        Run the kernel's CRC tool asynchronously.

        Fix mode (check=False) overwrites `modified_path` in place; the target CRC comes
        from `target_crc` (hex, e.g. "0x1A2B3C4D") or, if omitted, from the CRC embedded
        in the file's own name.

        Check mode (check=True) only computes/compares and modifies nothing; pass a second
        file as `reference_path` to compare two files against each other.

        Args:
            modified_path: Path to the file to fix or check
            reference_path: Second file to compare against (check mode only)
            target_crc: Target CRC as a hex string (fix mode; optional)
            check: Only calculate and compare CRC, do not modify any files
            no_backup: Do not create a .backup before fixing (fix mode)

        Returns:
            Tuple of (modified_path in fix mode / None in check mode, full_log)

        Note:
            The kernel never calls sys.exit(), so a failed fix still exits 0 — which is
            why failures below are detected from stdout rather than the return code.
        """
        args = ["crc", str(modified_path)]

        if check and reference_path:
            args.append(str(reference_path))

        if target_crc:
            args.extend(["--target-crc", target_crc])

        if check:
            args.append("--check")
        elif no_backup:
            args.append("--no-backup")

        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)

        full_log = self._build_log(cmd, stdout, stderr, returncode)

        if returncode != 0:
            raise RuntimeError(f"CRC correction failed: {stderr or stdout}", full_log)

        # The kernel logs failures but still exits 0 — detect them from stdout.
        if not check:
            if "CRC Fix Failed" in stdout:
                raise RuntimeError(
                    "CRC correction failed: the CLI could not fix the file's CRC.",
                    full_log
                )
            if "Could not extract target CRC" in stdout:
                raise RuntimeError(
                    "CRC correction failed: no target CRC. Provide one explicitly or use a filename that carries a CRC.",
                    full_log
                )

        # Fix mode modifies the file in place; check mode changes nothing.
        return (None if check else modified_path), full_log

    async def run_parse(
        self,
        filenames: List[str],
        bacii_path: Optional[Path] = None,
        index_column: Optional[str] = None,
        name_field: str = "full_name"
    ) -> Tuple[str, str]:
        """
        Run the kernel's `parse` command on one or more bundle filenames.

        Args:
            filenames: Filenames (or paths; only the name part is used) to parse
            bacii_path: Optional BA-Characters-Internal-ID.csv for character name lookup
            index_column: CSV column used as the lookup key
            name_field: Character name field to display

        Returns:
            Tuple of (stdout, full_log)
        """
        args = ["parse"] + [str(f) for f in filenames]

        if bacii_path:
            args.extend(["--bacii-path", str(bacii_path)])
        if index_column:
            args.extend(["--index-column", index_column])
        if name_field:
            args.extend(["--name-field", name_field])

        cmd = ["uv", "run", "bamt-cli"] + args
        returncode, stdout, stderr = await self._run_command(args)

        full_log = self._build_log(cmd, stdout, stderr, returncode)

        if returncode != 0:
            raise RuntimeError(f"Parse failed: {stderr or stdout}", full_log)

        return stdout, full_log


# Global CLI runner instance
cli_runner = CLIRunner()
