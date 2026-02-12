from .models import Notification
import subprocess
import os
from pathlib import Path
from datetime import datetime


def notifications(request):
    if request.user.is_authenticated:
        return {
            'unread_notifications': Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at'),
            'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count(),
        }
    return {}


def _get_git_commit():
    """Resolve a short git commit id.

    Order of resolution:
    - environment variables `GIT_COMMIT_SHORT` or `GIT_COMMIT`
    - run `git rev-parse --short HEAD` if git is present
    - read `GIT_COMMIT` file at project root
    - fallback to empty string
    """
    # 1) env vars
    commit = os.environ.get("GIT_COMMIT_SHORT") or os.environ.get("GIT_COMMIT")
    if commit:
        return commit

    # project root (two levels up from this file: diamond_web/ -> project root)
    repo_dir = Path(__file__).resolve().parent.parent

    # 2) try git command
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=0.5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass

    # 3) read GIT_COMMIT file if present
    try:
        commit_file = repo_dir / "GIT_COMMIT"
        if commit_file.exists():
            return commit_file.read_text().strip()
    except Exception:
        pass

    return ""


# Resolve once at import time to avoid invoking git on every request
GIT_COMMIT = _get_git_commit()


def _get_git_long_and_date(repo_dir: Path):
    """Try to resolve long commit id and authored date for the current HEAD."""
    long_sha = ""
    date_str = ""
    try:
        res = subprocess.run([
            "git",
            "log",
            "-1",
            "--format=%H;%cI",
        ], cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=0.5)
        if res.returncode == 0 and res.stdout:
            part = res.stdout.strip().split(";")
            if len(part) >= 1:
                long_sha = part[0]
            if len(part) >= 2:
                date_str = part[1]
    except Exception:
        pass

    # Fallback: environment variables
    if not long_sha:
        long_sha = os.environ.get("GIT_COMMIT_LONG") or os.environ.get("GIT_COMMIT") or ""
    if not date_str:
        date_str = os.environ.get("GIT_COMMIT_DATE") or ""

    return long_sha, date_str


def _get_git_branch(repo_dir: Path):
    try:
        res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=0.5)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return os.environ.get("GIT_BRANCH", "")


def git_commit(request):
    """Expose commit metadata to templates.

    Variables provided:
    - `git_commit`: short sha (string)
    - `git_commit_info`: dict with keys `short`, `long`, `date`, `branch`
    """
    repo_dir = Path(__file__).resolve().parent.parent
    long_sha, date_str = _get_git_long_and_date(repo_dir)
    branch = _get_git_branch(repo_dir)

    # Normalize date for display if present
    commit_date_display = ""
    if date_str:
        try:
            # ISO 8601 -> local display
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            commit_date_display = dt.strftime('%Y-%m-%d %H:%M:%S %z')
        except Exception:
            commit_date_display = date_str

    info = {
        "short": GIT_COMMIT or "",
        "long": long_sha or "",
        "date": commit_date_display,
        "branch": branch or "",
    }
    return {"git_commit": info["short"], "git_commit_info": info}