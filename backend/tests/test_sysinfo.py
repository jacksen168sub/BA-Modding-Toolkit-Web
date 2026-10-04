# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

"""Tests for the container / cgroup aware system readings.

The cgroup filesystem is faked on disk and ``CGROUP_ROOT`` pointed at it, so
both the cgroup v1 and v2 layouts are covered without needing Docker.
"""

import pytest

from app.utils import sysinfo

GIB = 1024 ** 3


@pytest.fixture
def cgroup_v2(tmp_path, monkeypatch):
    """A cgroup v2 hierarchy limited to 2 CPUs and 4 GiB."""
    root = tmp_path / "cgroup"
    root.mkdir()
    (root / "cgroup.controllers").write_text("cpuset cpu io memory\n")
    (root / "cpu.max").write_text("200000 100000")
    (root / "memory.max").write_text(str(4 * GIB))
    (root / "memory.current").write_text(str(GIB))
    (root / "cpu.stat").write_text("usage_usec 10000000\nuser_usec 8000000\nsystem_usec 2000000\n")

    monkeypatch.setattr(sysinfo, "CGROUP_ROOT", root)
    monkeypatch.setattr(sysinfo, "_prev_container_cpu", None)
    return root


@pytest.fixture
def cgroup_v1(tmp_path, monkeypatch):
    """A cgroup v1 hierarchy limited to 1.5 CPUs and 2 GiB."""
    root = tmp_path / "cgroup"
    for sub in ("cpu", "memory", "cpuacct"):
        (root / sub).mkdir(parents=True)
    (root / "cpu" / "cpu.cfs_quota_us").write_text("150000")
    (root / "cpu" / "cpu.cfs_period_us").write_text("100000")
    (root / "memory" / "memory.limit_in_bytes").write_text(str(2 * GIB))
    (root / "memory" / "memory.usage_in_bytes").write_text(str(GIB // 2))
    (root / "cpuacct" / "cpuacct.usage").write_text("5000000000")

    monkeypatch.setattr(sysinfo, "CGROUP_ROOT", root)
    monkeypatch.setattr(sysinfo, "_prev_container_cpu", None)
    return root


@pytest.fixture
def no_cgroup(tmp_path, monkeypatch):
    """No cgroup filesystem visible at all."""
    root = tmp_path / "cgroup"
    root.mkdir()
    monkeypatch.setattr(sysinfo, "CGROUP_ROOT", root)
    return root


def test_cgroup_v2_limits_are_read(cgroup_v2):
    info = sysinfo.container_info()
    assert info["detected"] is True
    assert info["cgroup_version"] == 2
    assert info["cpu_quota"] == 2.0
    assert info["memory_limit"] == 4 * GIB


def test_cgroup_v1_limits_are_read(cgroup_v1):
    info = sysinfo.container_info()
    assert info["detected"] is True
    assert info["cgroup_version"] == 1
    assert info["cpu_quota"] == 1.5
    assert info["memory_limit"] == 2 * GIB


def test_cpu_is_reported_against_the_container_quota(cgroup_v2, tmp_path):
    cpu = sysinfo.cpu_stats(sysinfo.container_info())
    # Effective cores come from the quota, not the host.
    assert cpu["quota"] == 2.0
    assert cpu["cores"] == 2
    assert cpu["host_cores"] == sysinfo.os.cpu_count()


def test_cpu_quota_is_rounded_up_to_whole_cores(cgroup_v1):
    cpu = sysinfo.cpu_stats(sysinfo.container_info())
    assert cpu["quota"] == 1.5
    assert cpu["cores"] == 2  # ceil(1.5)


def test_cpu_percent_uses_cgroup_usage(cgroup_v2, monkeypatch):
    """0.5 CPU-seconds over a ~1s window against a 2-core quota is ~25%."""
    (cgroup_v2 / "cpu.stat").write_text("usage_usec 10500000\n")
    monkeypatch.setattr(
        sysinfo, "_prev_container_cpu", (10_000_000, sysinfo.time.monotonic() - 1.0)
    )
    percent = sysinfo.cpu_stats(sysinfo.container_info())["percent"]
    assert 24.0 <= percent <= 25.0, percent


def test_memory_uses_the_container_limit(cgroup_v2, tmp_path):
    memory = sysinfo.memory_stats(sysinfo.container_info())
    assert memory["limit"] == 4 * GIB
    assert memory["total"] == 4 * GIB
    assert memory["used"] == GIB
    assert memory["percent"] == 25.0
    # Host total stays available for the (redactable) host section.
    assert memory["host_total"] and memory["host_total"] > 4 * GIB


def test_unlimited_memory_falls_back_to_host_figures(tmp_path, monkeypatch):
    root = tmp_path / "cgroup"
    for sub in ("cpu", "memory", "cpuacct"):
        (root / sub).mkdir(parents=True)
    (root / "memory" / "memory.limit_in_bytes").write_text(str(2**62))
    (root / "memory" / "memory.usage_in_bytes").write_text(str(GIB // 2))
    monkeypatch.setattr(sysinfo, "CGROUP_ROOT", root)
    monkeypatch.setattr(sysinfo, "_prev_container_cpu", None)

    memory = sysinfo.memory_stats(sysinfo.container_info())
    assert memory["limit"] is None
    assert memory["total"] == memory["host_total"]


def test_no_cgroup_filesystem_is_not_a_container(no_cgroup):
    info = sysinfo.container_info()
    assert info["detected"] is False
    assert info["cpu_quota"] is None
    assert info["memory_limit"] is None


def test_container_aware_can_be_disabled(cgroup_v2):
    stats = sysinfo.system_stats(cgroup_v2, container_aware=False)
    assert stats["container"]["detected"] is False
    assert stats["cpu"]["quota"] is None
    assert stats["memory"]["limit"] is None
