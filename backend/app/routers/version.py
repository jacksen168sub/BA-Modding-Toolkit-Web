import json
import os
import subprocess
import tomllib
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(tags=["Version"])

# Cache version info
_version_info = None

VERSION_FILE = Path(__file__).parent.parent.parent / "version.json"
PYPROJECT_FILE = Path(__file__).parent.parent.parent / "pyproject.toml"


def get_version_info():
    """Get version info from version.json, pyproject.toml, env, or git command."""
    global _version_info

    if _version_info is not None:
        return _version_info

    result = {
        "tag": None,
        "commit": None,
        "version": "unknown"
    }

    # 1. Try version.json (written at Docker build time)
    if VERSION_FILE.exists():
        try:
            with open(VERSION_FILE, "r") as f:
                data = json.load(f)
            result["version"] = data.get("version", "unknown")
            result["tag"] = data.get("tag")
            result["commit"] = data.get("commit")
            _version_info = result
            return result
        except Exception:
            pass

    # 2. Fallback: read pyproject.toml directly
    if PYPROJECT_FILE.exists():
        try:
            with open(PYPROJECT_FILE, "rb") as f:
                data = tomllib.load(f)
            ver = data.get("project", {}).get("version", "")
            if ver:
                result["version"] = f"v{ver}"
        except Exception:
            pass

    # 3. Supplement with env variables (for git tag/commit)
    env_tag = os.environ.get("GIT_TAG", "")
    env_commit = os.environ.get("GIT_COMMIT", "")

    if env_tag:
        result["tag"] = env_tag
    if env_commit:
        result["commit"] = env_commit

    # 4. Fallback: try git command (for local development)
    if not result["tag"] or not result["commit"]:
        try:
            project_root = Path(__file__).parent.parent.parent.parent

            if not result["commit"]:
                commit = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root)
                )
                if commit.returncode == 0:
                    result["commit"] = commit.stdout.strip()

            if not result["tag"]:
                tag = subprocess.run(
                    ["git", "describe", "--tags", "--exact-match"],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root)
                )
                if tag.returncode == 0:
                    result["tag"] = tag.stdout.strip()
        except Exception:
            pass

    # Build version string if not already set from version.json
    if result["version"] == "unknown":
        if result["tag"]:
            result["version"] = f"{result['tag']} ({result['commit']})"
        elif result["commit"]:
            result["version"] = result["commit"]

    _version_info = result
    return result


@router.get("/version")
def get_version():
    """Get application version info."""
    info = get_version_info()
    return {
        "tag": info["tag"],
        "commit": info["commit"],
        "version": info["version"]
    }