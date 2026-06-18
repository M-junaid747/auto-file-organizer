"""
deduper.py
----------
Handles duplicate detection via content hashing.

Two files with identical content (regardless of filename) produce the
same SHA256 hash. We use this to catch the very common case of the
same file downloaded multiple times under different names
(e.g. "report.pdf" and "report (1).pdf").

Hashing is done in chunks so large video files don't get fully loaded
into memory at once.
"""

import hashlib
from pathlib import Path

CHUNK_SIZE = 8192  # 8 KB per read — safe for large files, fast for small ones


def compute_file_hash(file_path: Path) -> str:
    """
    Compute the SHA256 hash of a file's contents.
    Returns the hex digest as a string.
    Raises OSError if the file cannot be read (e.g. locked by another process).
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def is_duplicate_in_current_run(file_hash: str, seen_hashes_this_run: set) -> bool:
    """
    Check if this hash has already appeared earlier in THIS run
    (separate from the database check, which covers PAST runs).
    """
    return file_hash in seen_hashes_this_run
