# Desktop Automation System

An advanced file-organizing automation system for Windows. Goes beyond a
basic "sort by extension" script with a configurable rules engine,
content-aware classification, duplicate detection, an undo log, a live
folder watcher, and HTML reporting.

## Features

- **Rules engine** — all sorting logic lives in `config/rules.yaml`. No
  code changes needed to add new file types or folders.
- **Content-aware sorting** — PDFs, DOCX, and TXT files are scanned for
  keywords (e.g. "invoice") and routed to a more specific subfolder than
  extension alone would suggest.
- **Duplicate detection** — SHA256 content hashing catches the same file
  downloaded under different names, both within a single run and across
  past runs (stored in SQLite).
- **Undo log** — every run is logged to `organized_log.db`. Running
  `python main.py --undo` reverts the most recent batch completely.
- **Age-based archiving** — files older than a configurable threshold
  with no content match get moved to an `Archive/` folder instead of
  cluttering the type folder.
- **Dry-run mode** — `python main.py --dry-run` shows exactly what would
  happen without touching a single file.
- **Live watcher** — `watcher.py` monitors the folder continuously and
  organizes new files within seconds of download, instead of waiting
  for the weekly scheduled run.
- **HTML + console reports** — every run prints a summary and saves a
  styled HTML report to `reports/`.
- **Weekly auto-run** — `setup_scheduled_task.bat` registers a Windows
  Task Scheduler job so the system runs hands-off, every week.

## Project Structure

```
desktop_automation/
├── main.py                      # Entry point: organize / dry-run / undo
├── watcher.py                    # Optional live folder monitor
├── setup_scheduled_task.bat      # Registers the weekly Task Scheduler job
├── requirements.txt
├── core/
│   ├── classifier.py             # Decides destination folder for each file
│   ├── deduper.py                  # SHA256 hashing for duplicate detection
│   ├── mover.py                     # Safe file moving + collision handling
│   ├── logger_db.py                  # SQLite history, used for undo
│   └── reporter.py                    # Console + HTML report generation
├── config/
│   └── rules.yaml                 # All sorting rules — edit this, not the code
├── reports/                       # Generated HTML reports (gitignored)
├── tests/
│   └── test_core.py                # Automated test suite (pytest)
└── organized_log.db               # SQLite database (created on first run, gitignored)
```

## Setup (Windows)

1. **Install Python 3.10+** if not already installed, from
   [python.org](https://www.python.org/downloads/). During installation,
   check "Add Python to PATH".

2. **Download or clone this project**, then open Command Prompt in the
   project folder.

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Edit `config/rules.yaml`:**
   - Set `source_folder` and `destination_root` to your actual Downloads
     path, e.g. `C:/Users/YourName/Downloads`.
   - Adjust extension rules, content keywords, and archive settings as
     you like.

5. **Test it safely first:**
   ```
   python main.py --dry-run
   ```
   This prints exactly what would happen without moving anything.

6. **Run it for real:**
   ```
   python main.py
   ```

7. **If something looks wrong, undo it:**
   ```
   python main.py --undo
   ```

## Running Automatically Every Week

Right-click `setup_scheduled_task.bat` and choose **"Run as administrator"**.
This registers a Windows Task Scheduler job named `DesktopAutomationWeekly`
that runs every Sunday at 9:00 AM.

To verify, change, or remove it later, open **Task Scheduler** from the
Start menu and look for that task name.

> **Note:** This script was written and synatx-checked against
> Microsoft's documented `schtasks` reference, but could not be executed
> live during development since the build environment is Linux-based.
> Test it once manually after setup (right-click the task in Task
> Scheduler → Run) to confirm it launches `main.py` correctly on your
> machine before relying on the weekly schedule.

## Running the Live Watcher (Optional)

Instead of waiting for the weekly run, you can keep a terminal open with:

```
python watcher.py
```

This watches your Downloads folder continuously and organizes new files
within a few seconds of them appearing. Stop it with `Ctrl+C`. To run it
automatically at every login, place a shortcut to it in your Windows
Startup folder (`Win+R` → `shell:startup`).

## Packaging as a Standalone .exe (No Python Required)

If you want to share this tool with someone who doesn't have Python
installed, or just want a clickable executable instead of a command
you have to remember:

1. On a **Windows machine**, open Command Prompt in the project folder.
2. Run `build_exe.bat`.
3. Find the result at `dist\DesktopAutomation.exe`.

This uses PyInstaller to bundle the script, all dependencies, and a
Python interpreter into one file. The resulting `.exe` runs the exact
same code, supports `--dry-run` and `--undo` exactly as before, and
needs nothing else installed on the target machine.

> **Why this matters and what was actually verified:** PyInstaller is
> not a cross-compiler — a Windows `.exe` can only be built by running
> PyInstaller on Windows itself. Since this project was built in a
> Linux environment, the *Windows* `.exe` itself could not be produced
> or tested here. What *was* verified, by building and running an
> equivalent Linux binary with the identical PyInstaller command and
> source code, is that the packaging approach is sound: the binary
> ran standalone, correctly read the YAML config, classified and moved
> files, and round-tripped through organize → undo across two separate
> process runs. One real bug was caught and fixed in this process —
> `BASE_DIR` originally resolved to PyInstaller's temporary extraction
> folder when frozen, which would have silently broken the undo log
> and reports (they'd vanish after each run instead of persisting next
> to the executable). The fix anchors `BASE_DIR` to `sys.executable`'s
> location when running as a frozen exe. Run `build_exe.bat` once after
> building and do a `--dry-run` followed by a real run and `--undo` to
> confirm it behaves identically on your actual Windows machine.

## Deployment Summary

This is a desktop automation tool, not a web service, so "deployment"
doesn't mean hosting on a server — there's no server involved, and it
needs direct access to your actual filesystem. The three legitimate,
free ways to "deploy" it are:

1. **Run with Python installed** (Option already covered above) — zero
   cost, most flexible, requires Python on the machine.
2. **Package as a standalone `.exe`** via `build_exe.bat` — zero cost,
   no Python needed on the target machine, build it once on Windows.
3. **Push to GitHub** for free, real version control and easy cloning
   onto any machine. This repository's full commit history (14 commits,
   from scaffold through testing through packaging) is ready to push to
   a new GitHub repo with `git remote add origin <url> && git push`.

There is no free *web hosting* option for this category of tool, and
claiming otherwise would be inaccurate — the closest equivalent is
Task Scheduler (Option A) or the live watcher, both of which are
already wired up and tested above.

## Running Tests

```
pip install pytest
pytest tests/test_core.py -v
```

All 14 tests should pass, covering classification precedence, duplicate
detection, collision-safe moving, undo/restore, and report generation.

## Configuration Reference (`config/rules.yaml`)

| Key | Purpose |
|---|---|
| `source_folder` | Folder being monitored and organized |
| `destination_root` | Where organized subfolders are created |
| `min_file_age_seconds` | Skip files newer than this (avoids grabbing mid-download files) |
| `extension_rules` | Map of folder name → list of extensions |
| `content_rules` | Keyword-based overrides for PDFs/DOCX/TXT |
| `archive_after_days` | Files older than this with no content match go to Archive |
| `fallback_folder` | Destination when nothing else matches |
| `duplicate_folder` | Destination for detected duplicates |
| `ignore_patterns` | Glob patterns to never touch (e.g. `*.tmp`) |

## How Classification Works (Precedence Order)

1. **Content rule match** (highest priority) — e.g. a `.txt` file
   containing "invoice" goes to `Documents/Invoices` even though the
   plain extension rule would send it to `Documents`.
2. **Extension rule**, possibly redirected by age-based archiving if the
   file is old and didn't match a content rule.
3. **Fallback folder**, if nothing else matched.

Duplicate detection happens *before* classification — if a file's
content hash has been seen before (in this run or a past one), it's
routed to `duplicate_folder` regardless of what classification would
otherwise decide.

## Known Limitations

- Content extraction only supports `.pdf`, `.docx`, and `.txt` — image
  or video content-awareness (e.g. detecting screenshots vs photos) is
  not implemented in this version.
- The watcher debounces by 5 seconds, so if you download many files in
  rapid succession, they may be processed across two consecutive runs
  rather than exactly one — this is intentional to keep the system
  simple and avoid race conditions, but is worth knowing about.
- Task Scheduler registration was built from Microsoft's documented
  `schtasks` syntax but not executed live in this environment — verify
  it manually once after setup as noted above.

## License

Personal/educational project — use and modify freely.
