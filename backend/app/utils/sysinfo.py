# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

"""Cross-platform system resource statistics.

``psutil`` is used when it is installed. When it is not, CPU / memory / disk
are read straight from the Linux ``/proc`` and ``os.statvfs`` interfaces so the
service still reports load inside stripped-down images.

Inside a container the host's ``/proc`` describes the whole machine, so the
cgroup limits are read as well and CPU / memory are reported relative to this
container's own quota instead of the host's totals.
"""

import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

if psutil is not None:
    # cpu_percent(interval=None) reports usage since the previous call, so the
    # very first call would always read 0. Prime it here to make the first
    # request meaningful.
    psutil.cpu_percent(interval=None)


CGROUP_ROOT = Path("/sys/fs/cgroup")

# cgroup v1 reports "no limit" as a value near 2**63.
_CGROUP_V1_UNLIMITED = 2**62

# Window used to take a first cgroup CPU sample that already has a delta.
_PRIME_WINDOW_SECONDS = 0.1

# /proc/stat needs two samples to derive a percentage, so keep the previous one.
_prev_cpu_sample: Optional[tuple] = None
_prev_container_cpu: Optional[tuple] = None


def _percent(numerator: float, denominator: float) -> Optional[float]:
    """Return a clamped 0-100 percentage, or None when it is undefined."""
    if not denominator:
        return None
    return round(max(0.0, min(100.0, 100.0 * numerator / denominator)), 1)


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def _read_int(path: Path) -> Optional[int]:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


# --- cgroup / container -------------------------------------------------


def _cgroup_version() -> Optional[int]:
    """2, 1, or None when no cgroup filesystem is visible."""
    if (CGROUP_ROOT / "cgroup.controllers").exists():
        return 2
    if (CGROUP_ROOT / "cpu" / "cpu.cfs_quota_us").exists():
        return 1
    if (CGROUP_ROOT / "memory" / "memory.limit_in_bytes").exists():
        return 1
    return None


def _container_runtime() -> Optional[str]:
    """Best-effort identification of the container runtime, or None."""
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return "kubernetes"
    if Path("/.dockerenv").exists():
        return "docker"
    if Path("/run/.containerenv").exists():
        return "podman"

    # Fall back to the init process's cgroup path.
    raw = _read_text(Path("/proc/1/cgroup")) or ""
    if "kubepods" in raw:
        return "kubernetes"
    if "docker" in raw or "containerd" in raw:
        return "docker"
    return None


def _cpu_quota_cores() -> Optional[float]:
    """CPU quota expressed in whole cores, or None when unlimited."""
    version = _cgroup_version()

    if version == 2:
        raw = _read_text(CGROUP_ROOT / "cpu.max")
        if not raw:
            return None
        parts = raw.split()
        if len(parts) < 2 or parts[0] == "max":
            return None
        try:
            quota, period = int(parts[0]), int(parts[1])
        except ValueError:
            return None
    elif version == 1:
        quota = _read_int(CGROUP_ROOT / "cpu" / "cpu.cfs_quota_us")
        period = _read_int(CGROUP_ROOT / "cpu" / "cpu.cfs_period_us")
        if quota is None or period is None:
            return None
    else:
        return None

    if quota <= 0 or period <= 0:
        return None
    return round(quota / period, 2)


def _container_memory() -> tuple:
    """(usage_bytes, limit_bytes) from the cgroup; limit is None when unlimited."""
    version = _cgroup_version()

    if version == 2:
        usage = _read_int(CGROUP_ROOT / "memory.current")
        raw = _read_text(CGROUP_ROOT / "memory.max")
        if raw in (None, "max"):
            return usage, None
        limit = None
        try:
            limit = int(raw)
        except ValueError:
            return usage, None
    elif version == 1:
        usage = _read_int(CGROUP_ROOT / "memory" / "memory.usage_in_bytes")
        limit = _read_int(CGROUP_ROOT / "memory" / "memory.limit_in_bytes")
        if limit is not None and limit >= _CGROUP_V1_UNLIMITED:
            limit = None
    else:
        return None, None

    if limit is not None and limit <= 0:
        limit = None
    return usage, limit


def _container_cpu_usage_usec() -> Optional[int]:
    """Cumulative CPU time consumed by this cgroup, in microseconds."""
    version = _cgroup_version()

    if version == 2:
        raw = _read_text(CGROUP_ROOT / "cpu.stat")
        if not raw:
            return None
        for line in raw.splitlines():
            if line.startswith("usage_usec"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        return None
        return None

    if version == 1:
        nanos = _read_int(CGROUP_ROOT / "cpuacct" / "cpuacct.usage")
        return nanos // 1000 if nanos is not None else None

    return None


def container_info() -> dict:
    """Container runtime and resource limits, if any apply to this process."""
    runtime = _container_runtime()
    cpu_quota = _cpu_quota_cores()
    _, memory_limit = _container_memory()

    detected = runtime is not None or cpu_quota is not None or memory_limit is not None
    return {
        "detected": detected,
        "runtime": runtime,
        "cgroup_version": _cgroup_version(),
        "cpu_quota": cpu_quota,
        "memory_limit": memory_limit,
    }


# --- host readings ------------------------------------------------------


def _proc_stat_sample() -> Optional[tuple]:
    """Return (idle_ticks, total_ticks) from /proc/stat, or None if unreadable."""
    try:
        with open("/proc/stat", "r") as f:
            first = f.readline()
    except OSError:
        return None

    if not first.startswith("cpu "):
        return None

    fields = [int(x) for x in first.split()[1:] if x.isdigit()]
    if len(fields) < 4:
        return None

    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle + iowait
    return idle, sum(fields)


def _proc_meminfo() -> Optional[dict]:
    """Parse /proc/meminfo into a {key: bytes} mapping, or None if unreadable."""
    try:
        info = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts:
                    info[key.strip()] = int(parts[0]) * 1024
        return info or None
    except (OSError, ValueError):
        return None


def _load_average() -> Optional[list]:
    """1/5/15 minute load average, or None where the concept does not apply."""
    if sys.platform.startswith("win"):
        # psutil emulates this on Windows but only ever reports zeros.
        return None
    try:
        if psutil is not None:
            return [round(v, 2) for v in psutil.getloadavg()]
        return [round(v, 2) for v in os.getloadavg()]
    except (OSError, AttributeError):
        return None


def _host_cpu_percent() -> Optional[float]:
    """Host-wide CPU utilisation."""
    global _prev_cpu_sample

    if psutil is not None:
        # Non-blocking: reports utilisation since the previous call.
        return psutil.cpu_percent(interval=None)

    sample = _proc_stat_sample()
    if not sample:
        return None

    percent = None
    if _prev_cpu_sample:
        d_idle = sample[0] - _prev_cpu_sample[0]
        d_total = sample[1] - _prev_cpu_sample[1]
        percent = _percent(d_total - d_idle, d_total)
    _prev_cpu_sample = sample
    return percent


def _container_cpu_percent(quota_cores: float) -> Optional[float]:
    """CPU utilisation relative to this container's quota."""
    global _prev_container_cpu

    usage = _container_cpu_usage_usec()
    if usage is None:
        return None

    if _prev_container_cpu is None:
        # No previous sample yet: take a short blocking one so the first
        # request already reports a real figure.
        start_time, start_usage = time.monotonic(), usage
        time.sleep(_PRIME_WINDOW_SECONDS)
        end_usage = _container_cpu_usage_usec()
        end_time = time.monotonic()
        if end_usage is None:
            return None
        _prev_container_cpu = (end_usage, end_time)
        return _percent(
            (end_usage - start_usage) / 1_000_000,
            (end_time - start_time) * quota_cores,
        )

    prev_usage, prev_time = _prev_container_cpu
    now = time.monotonic()
    _prev_container_cpu = (usage, now)

    elapsed = now - prev_time
    if elapsed <= 0:
        return None
    return _percent((usage - prev_usage) / 1_000_000, elapsed * quota_cores)


def _host_memory() -> dict:
    """Host-wide physical memory usage."""
    if psutil is not None:
        vm = psutil.virtual_memory()
        return {
            "total": vm.total,
            "used": vm.total - vm.available,
            "available": vm.available,
            "percent": round(vm.percent, 1),
        }

    info = _proc_meminfo()
    if not info or "MemTotal" not in info:
        return {"total": None, "used": None, "available": None, "percent": None}

    total = info["MemTotal"]
    available = info.get("MemAvailable")
    if available is None:
        available = info.get("MemFree", 0) + info.get("Buffers", 0) + info.get("Cached", 0)

    used = total - available
    return {
        "total": total,
        "used": used,
        "available": available,
        "percent": _percent(used, total),
    }


# --- public readings ----------------------------------------------------


def cpu_stats(container: dict) -> dict:
    """CPU utilisation plus topology, relative to the container quota if any."""
    host_cores = os.cpu_count() or 1
    quota = container.get("cpu_quota")

    effective_cores = max(1, int(math.ceil(quota))) if quota else host_cores

    if quota and container.get("detected"):
        percent = _container_cpu_percent(quota)
    else:
        percent = _host_cpu_percent()

    return {
        "percent": round(percent, 1) if percent is not None else None,
        "cores": effective_cores,
        "host_cores": host_cores,
        "quota": quota,
        "load_avg": _load_average(),
    }


def memory_stats(container: dict) -> dict:
    """Memory usage, capped by the container limit when one is set."""
    result = _host_memory()
    result["host_total"] = result["total"]
    result["limit"] = None

    usage, limit = _container_memory()
    if container.get("detected") and limit:
        result["total"] = limit
        result["limit"] = limit
        if usage is not None:
            result["used"] = usage
            result["available"] = max(0, limit - usage)
            result["percent"] = _percent(usage, limit)

    return result


def disk_stats(path: Path) -> dict:
    """Disk usage of the filesystem holding ``path``."""
    empty = {"path": str(path), "total": None, "used": None, "free": None, "percent": None}

    if psutil is not None:
        try:
            du = psutil.disk_usage(str(path))
            return {
                "path": str(path),
                "total": du.total,
                "used": du.used,
                "free": du.free,
                "percent": round(du.percent, 1),
            }
        except OSError:
            pass

    try:
        st = os.statvfs(str(path))
    except (OSError, AttributeError):
        return empty

    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - st.f_bfree * st.f_frsize
    return {
        "path": str(path),
        "total": total,
        "used": used,
        "free": free,
        "percent": _percent(used, total),
    }


def process_stats() -> dict:
    """Resource usage and start time of the backend process itself."""
    if psutil is None:
        return {
            "pid": os.getpid(),
            "memory_rss": None,
            "cpu_percent": None,
            "threads": None,
            "started_at": None,
        }

    proc = psutil.Process()
    with proc.oneshot():
        mem = proc.memory_info()
        return {
            "pid": proc.pid,
            "memory_rss": mem.rss,
            "cpu_percent": round(proc.cpu_percent(interval=None), 1),
            "threads": proc.num_threads(),
            "started_at": datetime.utcfromtimestamp(proc.create_time()),
        }


def system_stats(disk_path: Path, container_aware: bool = True) -> dict:
    """Assemble the full system block for the status endpoint."""
    container = container_info() if container_aware else {
        "detected": False,
        "runtime": None,
        "cgroup_version": None,
        "cpu_quota": None,
        "memory_limit": None,
    }

    return {
        "container": container,
        "cpu": cpu_stats(container),
        "memory": memory_stats(container),
        "disk": disk_stats(disk_path),
        "process": process_stats(),
    }
