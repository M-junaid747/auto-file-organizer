"""
classifier.py
--------------
Decides WHERE a file should go. This is the brain of the rules engine.

Classification happens in passes, each one able to override the last:

  Pass 1 (extension_rules):   .pdf -> "Documents", .jpg -> "Images", etc.
  Pass 2 (content_rules):     if it's a PDF/DOCX/TXT and its text matches
                               a keyword, override to a more specific folder
                               e.g. "Documents" -> "Documents/Invoices"
  Pass 3 (archive_after_days): if the file is older than the configured
                               threshold AND no content rule matched,
                               redirect it into the Archive folder instead.

If nothing matches at all, the file goes to `fallback_folder`.

Content extraction failures (corrupted file, encrypted PDF, etc.) are
caught and simply skipped — classification falls back to the extension
rule rather than crashing the whole run.
"""

import fnmatch
import time
from pathlib import Path

# pypdf and python-docx are optional at import time — if a user only
# wants extension-based sorting, the script should still run without
# them installed. We import lazily inside the extraction functions.


def matches_ignore_pattern(filename: str, ignore_patterns: list[str]) -> bool:
    """Check if filename matches any of the glob-style ignore patterns."""
    return any(fnmatch.fnmatch(filename, pattern) for pattern in ignore_patterns)


def is_old_enough_to_process(file_path: Path, min_age_seconds: int) -> bool:
    """
    Return True if the file's last modification time is older than
    min_age_seconds ago — i.e. it's safe to assume the file is no
    longer being actively written to (e.g. mid-download).
    """
    age_seconds = time.time() - file_path.stat().st_mtime
    return age_seconds >= min_age_seconds


def get_extension_folder(file_path: Path, extension_rules: dict) -> str | None:
    """
    Pass 1: Look up the file's extension against extension_rules.
    Returns the destination folder name, or None if no extension matches.
    """
    ext = file_path.suffix.lower()
    for folder_name, extensions in extension_rules.items():
        if ext in extensions:
            return folder_name
    return None


def extract_text_snippet(file_path: Path, max_chars: int = 3000) -> str:
    """
    Extract a text snippet from the start of a file for keyword matching.
    Supports .txt, .pdf, .docx. Returns an empty string on any failure
    (corrupted file, encrypted PDF, unsupported format, etc.) — this
    function must NEVER raise, since a single bad file should not
    stop the whole batch.
    """
    ext = file_path.suffix.lower()

    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars).lower()

        elif ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            text = ""
            for page in reader.pages[:2]:  # first 2 pages is enough for classification
                text += page.extract_text() or ""
                if len(text) >= max_chars:
                    break
            return text[:max_chars].lower()

        elif ext == ".docx":
            from docx import Document

            doc = Document(str(file_path))
            text = " ".join(p.text for p in doc.paragraphs[:50])
            return text[:max_chars].lower()

    except Exception:
        # Deliberately broad: any extraction failure just means
        # "no content signal available" — not a fatal error.
        return ""

    return ""


def get_content_override(file_path: Path, content_rules: list[dict]) -> str | None:
    """
    Pass 2: Check extracted text against content_rules keywords.
    Returns the override destination (e.g. "Documents/Invoices") or
    None if no keyword matched or the file type isn't supported for
    content extraction.
    """
    if file_path.suffix.lower() not in (".pdf", ".docx", ".txt"):
        return None

    text = extract_text_snippet(file_path)
    if not text:
        return None

    for rule in content_rules:
        for keyword in rule["keywords"]:
            if keyword.lower() in text:
                return rule["destination"]

    return None


def get_age_override(
    file_path: Path, archive_after_days: int, archive_folder_name: str
) -> str | None:
    """
    Pass 3: If archiving is enabled (archive_after_days > 0) and the
    file is older than that threshold, return the archive folder name.
    """
    if archive_after_days <= 0:
        return None

    age_days = (time.time() - file_path.stat().st_mtime) / 86400
    if age_days >= archive_after_days:
        return archive_folder_name

    return None


def classify_file(file_path: Path, config: dict) -> str:
    """
    Run all classification passes in order and return the final
    destination folder (relative path string, e.g. "Documents/Invoices").

    Precedence (highest wins):
      1. Content-aware rule match (most specific intent)
      2. Extension-based folder, possibly overridden by age-based archiving
      3. Fallback folder
    """
    extension_folder = get_extension_folder(file_path, config["extension_rules"])

    content_override = get_content_override(file_path, config.get("content_rules", []))
    if content_override:
        return content_override

    if extension_folder:
        age_override = get_age_override(
            file_path,
            config.get("archive_after_days", 0),
            config.get("archive_folder_name", "Archive"),
        )
        if age_override:
            return age_override
        return extension_folder

    return config.get("fallback_folder", "Misc")
