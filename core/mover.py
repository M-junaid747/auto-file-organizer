"""
mover.py
---------
Performs the actual file move on disk, after classification and
duplicate-checking have already decided what should happen.

Responsibilities:
  - Create destination folders if they don't exist yet.
  - Resolve filename collisions (same name, different content) by
    appending a timestamp suffix rather than silently overwriting.
  - Wrap shutil.move in error handling so one bad file (permissions,
    locked file, etc.) doesn't crash the entire batch.
"""

import shutil
from datetime import datetime
from pathlib import Path


def resolve_destination_path(destination_folder: Path, file_path: Path) -> Path:
    """
    Build the final destination path for a file, handling name
    collisions. If a file with the same name already exists at the
    destination, append a timestamp to keep both rather than
    overwriting one silently.
    """
    destination_folder.mkdir(parents=True, exist_ok=True)
    target_path = destination_folder / file_path.name

    if not target_path.exists():
        return target_path

    # Collision: same filename already present at destination.
    # Append a timestamp to the stem so nothing is lost.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    return destination_folder / new_name


def move_file(file_path: Path, destination_root: Path, relative_folder: str) -> tuple[bool, str, Path | None]:
    """
    Move a single file into destination_root/relative_folder.

    Returns a tuple of (success: bool, message: str, final_path: Path|None).
    Never raises — all errors are caught and reported back so the
    calling loop can continue processing remaining files.
    """
    destination_folder = destination_root / relative_folder

    try:
        final_path = resolve_destination_path(destination_folder, file_path)
        shutil.move(str(file_path), str(final_path))
        return True, "moved successfully", final_path
    except PermissionError:
        return False, "permission denied (file may be open elsewhere)", None
    except FileNotFoundError:
        return False, "file disappeared before it could be moved", None
    except OSError as e:
        return False, f"OS error: {e}", None


def restore_file(original_path: str, current_path: str) -> tuple[bool, str]:
    """
    Used by the undo command: move a file from its current
    (organized) location back to its original location.
    """
    current = Path(current_path)
    original = Path(original_path)

    if not current.exists():
        return False, "file no longer exists at its organized location"

    try:
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(original))
        return True, "restored successfully"
    except OSError as e:
        return False, f"OS error during restore: {e}"
