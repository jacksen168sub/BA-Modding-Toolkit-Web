import subprocess
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(tags=["Version"])

# Cache version info
_version_info = None


def get_git_info():
    """Get git tag and commit hash."""
    global _version_info
    
    if _version_info is not None:
        return _version_info
    
    result = {
        "tag": None,
        "commit": None,
        "version": "unknown"
    }
    
    try:
        # Get git root directory
        git_dir = Path(__file__).parent.parent.parent.parent / ".git"
        
        if git_dir.exists():
            # Get current commit hash (short)
            commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                cwd=str(git_dir.parent)
            )
            if commit.returncode == 0:
                result["commit"] = commit.stdout.strip()
            
            # Get current tag
            tag = subprocess.run(
                ["git", "describe", "--tags", "--exact-match"],
                capture_output=True,
                text=True,
                cwd=str(git_dir.parent)
            )
            if tag.returncode == 0:
                result["tag"] = tag.stdout.strip()
            
            # Build version string
            if result["tag"]:
                result["version"] = f"{result['tag']} ({result['commit']})"
            elif result["commit"]:
                result["version"] = result["commit"]
    except Exception:
        pass
    
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
