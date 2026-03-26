"""Pre-startup cache cleanup for the backend codebase.

Removes only known cache artifacts and safe temporary cache-like files.
"""

from __future__ import annotations

import shutil
from pathlib import Path

CACHE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".cache",
}

CACHE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
}

# Safe temporary cache-like files commonly created during tooling/test runs.
TEMP_FILE_SUFFIXES = {
    ".tmp",
    ".temp",
}


def _is_env_file(path: Path) -> bool:
    name = path.name.lower()
    return name == ".env" or name.startswith(".env.")


def clear_all_caches(base_path: str) -> dict[str, int]:
    """Recursively remove known cache files and directories under base_path.

    The operation is idempotent and error-tolerant. It never raises for
    missing paths or deletion failures.
    """
    root = Path(base_path)
    summary = {"directories_deleted": 0, "files_deleted": 0, "errors": 0}

    if not root.exists() or not root.is_dir():
        return summary

    # Delete cache directories first to avoid double work on files under them.
    for current in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        try:
            if not current.exists() or not current.is_dir():
                continue
            if current.name in CACHE_DIR_NAMES:
                shutil.rmtree(current, ignore_errors=False)
                summary["directories_deleted"] += 1
        except Exception:
            summary["errors"] += 1

    # Delete cache files and safe temp files.
    for file_path in root.rglob("*"):
        try:
            if not file_path.exists() or not file_path.is_file():
                continue

            if _is_env_file(file_path):
                continue

            suffix = file_path.suffix.lower()
            if suffix in CACHE_FILE_SUFFIXES:
                file_path.unlink(missing_ok=True)
                summary["files_deleted"] += 1
            elif suffix in TEMP_FILE_SUFFIXES and file_path.name.lower().startswith(("pytest-", "tmp", ".tmp")):
                file_path.unlink(missing_ok=True)
                summary["files_deleted"] += 1
        except Exception:
            summary["errors"] += 1

    return summary
