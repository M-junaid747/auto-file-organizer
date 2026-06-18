"""
main.py
--------
Entry point for the Desktop Automation System.

Usage:
    python main.py                  Run a normal organize pass
    python main.py --dry-run        Show what WOULD happen, touch nothing
    python main.py --undo           Revert the most recent run
    python main.py --config PATH    Use a config file other than the default

This script is what Windows Task Scheduler calls weekly, and what
watcher.py calls every time a new file appears (see watcher.py).
"""

import argparse
import sys
from pathlib import Path

import yaml

from core import classifier, deduper, logger_db, mover, reporter

# When packaged into a standalone exe with PyInstaller, __file__ resolves
# to a temporary extraction folder (e.g. /tmp/_MEIxxxxxx or a Windows
# AppData temp path) that gets wiped after the process exits. That would
# silently break the undo log and reports, since they'd never persist
# between runs. sys.frozen + sys.executable give us the REAL location
# of the .exe itself, which is what we want the database and reports
# folder anchored to instead.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "rules.yaml"


def load_config(config_path: Path) -> dict:
    """Load and validate the YAML rules file. Exits with a clear error if invalid."""
    if not config_path.exists():
        print(f"ERROR: config file not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    required_keys = ["source_folder", "destination_root", "extension_rules"]
    missing = [k for k in required_keys if k not in config]
    if missing:
        print(f"ERROR: config is missing required keys: {missing}")
        sys.exit(1)

    return config


def collect_candidate_files(source_folder: Path, destination_root: Path, ignore_patterns: list, min_age_seconds: int) -> list[Path]:
    """
    Scan source_folder and return the list of files eligible for processing.
    Skips: subfolders (including ones we created, like Documents/),
    files matching ignore_patterns, and files that are too new (still downloading).
    """
    candidates = []

    if not source_folder.exists():
        print(f"ERROR: source folder does not exist: {source_folder}")
        sys.exit(1)

    for entry in source_folder.iterdir():
        if entry.is_dir():
            continue  # never descend into subfolders, including our own organized ones
        if classifier.matches_ignore_pattern(entry.name, ignore_patterns):
            continue
        if not classifier.is_old_enough_to_process(entry, min_age_seconds):
            continue
        candidates.append(entry)

    return candidates


def run_organize(config: dict, dry_run: bool = False) -> None:
    """
    The main workflow: scan -> dedupe -> classify -> move -> log -> report.
    If dry_run is True, every decision is computed and printed, but
    no file is actually moved and nothing is written to the database.
    """
    source_folder = Path(config["source_folder"])
    destination_root = Path(config["destination_root"])
    ignore_patterns = config.get("ignore_patterns", [])
    min_age_seconds = config.get("min_file_age_seconds", 60)
    duplicate_folder = config.get("duplicate_folder", "Duplicates")

    db_path = logger_db.get_db_path(BASE_DIR)
    if not dry_run:
        logger_db.init_db(db_path)

    batch_id = logger_db.new_batch_id() if not dry_run else "DRY-RUN"

    files = collect_candidate_files(source_folder, destination_root, ignore_patterns, min_age_seconds)

    if not files:
        print("No eligible files found. Downloads folder is already tidy.")
        return

    print(f"Found {len(files)} file(s) to process{' (DRY RUN — no changes will be made)' if dry_run else ''}...\n")

    results = []
    space_freed_bytes = 0
    seen_hashes_this_run = set()

    for file_path in files:
        try:
            file_size = file_path.stat().st_size
            file_hash = deduper.compute_file_hash(file_path)
        except OSError as e:
            results.append({
                "filename": file_path.name, "action": "error",
                "destination": "-", "detail": f"could not read file: {e}",
            })
            continue

        # Duplicate check: either seen earlier in this run, or seen in a past run
        is_dup = deduper.is_duplicate_in_current_run(file_hash, seen_hashes_this_run)
        if not is_dup and not dry_run:
            is_dup = logger_db.is_known_hash(db_path, file_hash)

        if is_dup:
            destination_folder = duplicate_folder
            action = "duplicate"
        else:
            destination_folder = classifier.classify_file(file_path, config)
            action = "archived" if destination_folder == config.get("archive_folder_name", "Archive") else "moved"

        seen_hashes_this_run.add(file_hash)

        if dry_run:
            results.append({
                "filename": file_path.name, "action": action,
                "destination": destination_folder, "detail": "[dry-run] would move here",
            })
            print(f"  [DRY-RUN] {file_path.name}  ->  {destination_folder}/")
            continue

        success, message, final_path = mover.move_file(file_path, destination_root, destination_folder)

        if success:
            results.append({
                "filename": file_path.name, "action": action,
                "destination": destination_folder, "detail": message,
            })
            logger_db.record_move(db_path, batch_id, str(file_path), str(final_path), file_hash, action)
            logger_db.record_hash(db_path, file_hash, str(final_path))
            space_freed_bytes += file_size
            print(f"  [OK] {file_path.name}  ->  {destination_folder}/")
        else:
            results.append({
                "filename": file_path.name, "action": "error",
                "destination": destination_folder, "detail": message,
            })
            print(f"  [FAILED] {file_path.name}: {message}")

    reporter.print_console_summary(results, space_freed_bytes)

    if not dry_run:
        report_path = reporter.generate_html_report(results, space_freed_bytes, BASE_DIR / "reports")
        print(f"HTML report saved to: {report_path}")


def run_undo() -> None:
    """Revert every move from the most recent (non-dry-run) batch."""
    db_path = logger_db.get_db_path(BASE_DIR)
    if not db_path.exists():
        print("No history found — nothing to undo.")
        return

    batch_id = logger_db.get_latest_batch_id(db_path)
    if not batch_id:
        print("No un-reverted batches found — nothing to undo.")
        return

    moves = logger_db.get_moves_for_batch(db_path, batch_id)
    if not moves:
        print("Latest batch has no moves recorded — nothing to undo.")
        return

    print(f"Undoing batch {batch_id} ({len(moves)} file(s))...\n")

    restored_count = 0
    for move_id, original_path, new_path, action_type in moves:
        success, message = mover.restore_file(original_path, new_path)
        if success:
            logger_db.mark_reverted(db_path, move_id)
            restored_count += 1
            print(f"  [RESTORED] {Path(original_path).name}")
        else:
            print(f"  [FAILED] {Path(original_path).name}: {message}")

    print(f"\nUndo complete: {restored_count}/{len(moves)} file(s) restored.")


def main():
    parser = argparse.ArgumentParser(description="Desktop Automation System — organize, dedupe, and report on your Downloads folder.")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without moving any files")
    parser.add_argument("--undo", action="store_true", help="Revert the most recent run")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH), help="Path to rules.yaml")
    args = parser.parse_args()

    if args.undo:
        run_undo()
        return

    config = load_config(Path(args.config))
    run_organize(config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
