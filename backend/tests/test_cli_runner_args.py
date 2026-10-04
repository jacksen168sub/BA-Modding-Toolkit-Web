# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub
#
# Contract tests for the CLI argument construction in app/services/cli_runner.py.
# They pin the argv the web backend hands to `bamt-cli` (kernel v2.9.2) so a future
# kernel bump that renames a flag fails a test instead of silently breaking a task.

import asyncio

import pytest

from app.services import cli_runner as cli_runner_mod
from app.services.cli_runner import CLIRunner


@pytest.fixture
def runner(monkeypatch, tmp_path):
    """A CLIRunner whose `_run_command` is stubbed to record argv.

    `returncode` / `stdout` are read from the dict so a test can script the response.
    """
    r = CLIRunner.__new__(CLIRunner)  # skip __init__ (no upstream checkout needed)
    r.upstream_dir = tmp_path
    r.timeout = 10
    captured = {"args": None, "returncode": 0, "stdout": "", "stderr": ""}

    async def fake_run_command(args, cwd=None):
        captured["args"] = list(args)
        return captured["returncode"], captured["stdout"], captured["stderr"]

    monkeypatch.setattr(r, "_run_command", fake_run_command)
    r.captured = captured
    return r


def _arg_value(args, flag):
    """Value following `flag`, or None."""
    return args[args.index(flag) + 1] if flag in args else None


# ------------------------- run_update (N-to-N) -------------------------

def test_run_update_builds_multi_source_multi_target_args(runner, tmp_path):
    sources = [tmp_path / "a.bundle", tmp_path / "b.bundle"]
    targets = [tmp_path / "x.bundle", tmp_path / "y.bundle"]
    out = tmp_path / "out"
    out.mkdir()
    runner.captured["stdout"] = "all_targets_unchanged"

    asyncio.run(runner.run_update(
        source_files=sources,
        target_files=targets,
        output_dir=out,
        crc_correction=False,
        asset_types=["Texture2D", "TextAsset"],
        strategy="cont_name_type",
        compression="lz4",
    ))

    args = runner.captured["args"]
    # `old` is a greedy positional, so every source must precede the first option.
    assert args[0] == "update"
    assert args[1:3] == [str(sources[0]), str(sources[1])]
    assert args[3] == "--output-dir"
    # --target takes all targets up to the next flag.
    t = args.index("--target")
    assert args[t + 1:t + 3] == [str(targets[0]), str(targets[1])]
    assert "--no-crc" in args
    assert _arg_value(args, "--strategy") == "cont_name_type"
    assert _arg_value(args, "--compression") == "lz4"
    # asset-types is n-ary: both values present before the next flag.
    a = args.index("--asset-types")
    assert args[a + 1:a + 3] == ["Texture2D", "TextAsset"]


def test_run_update_keeps_crc_flag_when_enabled(runner, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    runner.captured["stdout"] = "all_targets_unchanged"

    asyncio.run(runner.run_update(
        source_files=[tmp_path / "a.bundle"],
        target_files=[tmp_path / "x.bundle"],
        output_dir=out,
        crc_correction=True,
    ))
    assert "--no-crc" not in runner.captured["args"]


def test_run_update_all_targets_unchanged_is_success_with_no_outputs(runner, tmp_path):
    """`all_targets_unchanged` means success — it must NOT raise, and yields no paths."""
    out = tmp_path / "out"
    out.mkdir()
    runner.captured["stdout"] = "some log\n✅ Operation Successful: all_targets_unchanged\n"

    paths, _ = asyncio.run(runner.run_update(
        source_files=[tmp_path / "a.bundle"],
        target_files=[tmp_path / "x.bundle"],
        output_dir=out,
    ))
    assert paths == []


def test_run_update_returns_every_output(runner, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "x.bundle").write_bytes(b"1")
    (out / "y.bundle").write_bytes(b"2")

    paths, _ = asyncio.run(runner.run_update(
        source_files=[tmp_path / "a.bundle"],
        target_files=[tmp_path / "x.bundle", tmp_path / "y.bundle"],
        output_dir=out,
    ))
    assert sorted(p.name for p in paths) == ["x.bundle", "y.bundle"]


def test_run_update_raises_when_no_output_and_no_signal(runner, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(FileNotFoundError):
        asyncio.run(runner.run_update(
            source_files=[tmp_path / "a.bundle"],
            target_files=[tmp_path / "x.bundle"],
            output_dir=out,
        ))


def test_run_update_raises_on_crc_soft_failure(runner, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    runner.captured["stdout"] = "CRC Correction failed. The final file \"x\" could not be generated."
    with pytest.raises(RuntimeError):
        asyncio.run(runner.run_update(
            source_files=[tmp_path / "a.bundle"],
            target_files=[tmp_path / "x.bundle"],
            output_dir=out,
        ))


# ------------------------- run_pack (multi-target) -------------------------

def test_run_pack_builds_multi_target_args(runner, tmp_path):
    folder = tmp_path / "assets"
    folder.mkdir()
    targets = [tmp_path / "a.bundle", tmp_path / "b.bundle"]
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.bundle").write_bytes(b"1")

    paths, _ = asyncio.run(runner.run_pack(
        asset_folder=folder,
        target_bundles=targets,
        output_dir=out,
        crc_correction=False,
        compression="lz4",
    ))

    args = runner.captured["args"]
    assert args[0] == "pack"
    b = args.index("--bundle")
    assert args[b + 1:b + 3] == [str(targets[0]), str(targets[1])]
    assert _arg_value(args, "--folder") == str(folder)
    assert "--no-crc" in args
    assert _arg_value(args, "--compression") == "lz4"
    assert [p.name for p in paths] == ["a.bundle"]


def test_run_pack_returns_every_output(runner, tmp_path):
    folder = tmp_path / "assets"
    folder.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.bundle").write_bytes(b"1")
    (out / "b.bundle").write_bytes(b"2")

    paths, _ = asyncio.run(runner.run_pack(
        asset_folder=folder,
        target_bundles=[tmp_path / "a.bundle", tmp_path / "b.bundle"],
        output_dir=out,
    ))
    assert sorted(p.name for p in paths) == ["a.bundle", "b.bundle"]


def test_run_pack_raises_when_nothing_matched(runner, tmp_path):
    """The kernel reports 'Operation Failed' when no assets matched any target."""
    folder = tmp_path / "assets"
    folder.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    runner.captured["stdout"] = "❌ Operation Failed: No matching assets to pack."
    with pytest.raises(RuntimeError):
        asyncio.run(runner.run_pack(
            asset_folder=folder,
            target_bundles=[tmp_path / "a.bundle"],
            output_dir=out,
        ))


# ------------------------- run_crc -------------------------

def test_run_crc_fix_uses_positional_file_and_no_backup(runner, tmp_path):
    f = tmp_path / "my_mod.bundle"
    asyncio.run(runner.run_crc(modified_path=f, check=False, no_backup=True))

    args = runner.captured["args"]
    assert args[0] == "crc"
    assert args[1] == str(f)
    assert "--no-backup" in args
    # The v2.9.2 CLI dropped --original and --check-only.
    assert "--original" not in args
    assert "--check-only" not in args


def test_run_crc_fix_with_explicit_target_crc(runner, tmp_path):
    f = tmp_path / "my_mod.bundle"
    asyncio.run(runner.run_crc(modified_path=f, target_crc="0x1A2B3C4D"))
    assert _arg_value(runner.captured["args"], "--target-crc") == "0x1A2B3C4D"


def test_run_crc_check_single_file(runner, tmp_path):
    f = tmp_path / "my_mod.bundle"
    modified, _ = asyncio.run(runner.run_crc(modified_path=f, check=True))
    args = runner.captured["args"]
    assert args == ["crc", str(f), "--check"]
    # Check mode writes nothing.
    assert modified is None


def test_run_crc_check_two_files(runner, tmp_path):
    f1 = tmp_path / "my_mod.bundle"
    f2 = tmp_path / "original.bundle"
    asyncio.run(runner.run_crc(modified_path=f1, reference_path=f2, check=True))
    assert runner.captured["args"] == ["crc", str(f1), str(f2), "--check"]


def test_run_crc_raises_on_fix_failure(runner, tmp_path):
    f = tmp_path / "my_mod.bundle"
    runner.captured["stdout"] = "❌ CRC Fix Failed."
    with pytest.raises(RuntimeError):
        asyncio.run(runner.run_crc(modified_path=f))


def test_run_crc_raises_when_no_target_crc_available(runner, tmp_path):
    f = tmp_path / "my_mod.bundle"
    runner.captured["stdout"] = "❌ Error: Could not extract target CRC from filename."
    with pytest.raises(RuntimeError):
        asyncio.run(runner.run_crc(modified_path=f))


# ------------------------- run_parse -------------------------

def test_run_parse_args(runner):
    runner.captured["stdout"] = "category: spinecharacters"
    out, _ = asyncio.run(runner.run_parse(["a.bundle", "b.bundle"], name_field="name_jp"))
    args = runner.captured["args"]
    assert args[0] == "parse"
    assert args[1:3] == ["a.bundle", "b.bundle"]
    assert _arg_value(args, "--name-field") == "name_jp"
    assert out == "category: spinecharacters"
