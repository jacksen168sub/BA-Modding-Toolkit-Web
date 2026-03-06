import os
import subprocess
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(tags=["Version"])

# Cache version info
_version_info = None


def get_git_info():
    """Get git tag and commit hash from env or git command."""
    global _version_info
    
    if _version_info is not None:
        return _version_info
    
    result = {
        "tag": None,
        "commit": None,
        "version": "unknown"
    }
    
    # First, try to get from environment variables (for Docker builds)
    env_tag = os.environ.get("GIT_TAG", "")
    env_commit = os.environ.get("GIT_COMMIT", "")
    
    if env_tag or env_commit:
        result["tag"] = env_tag if env_tag else None
        result["commit"] = env_commit if env_commit else None
        
        if result["tag"]:
            result["version"] = f"{result['tag']} ({result['commit']})"
        elif result["commit"]:
            result["version"] = result["commit"]
        
        _version_info = result
        return result
    
    # Fallback: try git command (for local development)
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        
        # Get current commit hash (short)
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )
        if commit.returncode == 0:
            result["commit"] = commit.stdout.strip()
        
        # Get current tag
        tag = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )
        if tag.returncode == 0:
            result["tag"] = tag.stdout.strip()
        
        # Build version string
        if result["tag"]:
            result["version"] = f"{result['tag']} ({result['commit']})"
        elif result["commit"]:
            result["version"] = result["commit"]
    except Exception as e:
        print(f"Error getting git info: {e}")
    
    _version_info = result
    return result


@router.get("/version")
def get_version():
    """Get application version info."""
    info = get_git_info()
    return {
        "tag": info["tag"],
        "commit": info["commit"],
        "version": info["version"]
    }
