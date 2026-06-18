"""
reporter.py
------------
Generates a human-readable summary of what happened in a run:
  - A console printout immediately after the run finishes.
  - An HTML file saved to reports/ for a persistent visual record.

This module only formats and writes — it does not decide what
happened (that's main.py's job, which collects the results list).
"""

from datetime import datetime
from pathlib import Path


def format_bytes(num_bytes: int) -> str:
    """Convert a byte count into a human-readable string (KB/MB/GB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def print_console_summary(results: list[dict], space_freed_bytes: int) -> None:
    """
    Print a clean console summary at the end of a run.
    results is a list of dicts, each with keys:
      filename, action ('moved'/'duplicate'/'archived'/'error'),
      destination, detail
    """
    moved = [r for r in results if r["action"] == "moved"]
    duplicates = [r for r in results if r["action"] == "duplicate"]
    archived = [r for r in results if r["action"] == "archived"]
    errors = [r for r in results if r["action"] == "error"]

    print("\n" + "=" * 50)
    print("DESKTOP AUTOMATION — RUN SUMMARY")
    print("=" * 50)
    print(f"Files moved:       {len(moved)}")
    print(f"Files archived:    {len(archived)}")
    print(f"Duplicates found:  {len(duplicates)}")
    print(f"Errors:            {len(errors)}")
    print(f"Space freed:       {format_bytes(space_freed_bytes)}")

    if errors:
        print("\nFiles that could NOT be processed:")
        for e in errors:
            print(f"  - {e['filename']}: {e['detail']}")

    print("=" * 50 + "\n")


def generate_html_report(results: list[dict], space_freed_bytes: int, reports_dir: Path) -> Path:
    """
    Write an HTML report summarizing the run and return its path.
    Kept deliberately simple (inline CSS, no external dependencies)
    so it works standalone with no internet connection.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = reports_dir / f"report_{timestamp}.html"

    moved = [r for r in results if r["action"] == "moved"]
    duplicates = [r for r in results if r["action"] == "duplicate"]
    archived = [r for r in results if r["action"] == "archived"]
    errors = [r for r in results if r["action"] == "error"]

    def rows_html(items: list[dict]) -> str:
        if not items:
            return "<tr><td colspan='3'><em>None</em></td></tr>"
        return "\n".join(
            f"<tr><td>{r['filename']}</td><td>{r.get('destination', '-')}</td><td>{r.get('detail', '-')}</td></tr>"
            for r in items
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Desktop Automation Report — {timestamp}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 40px; background: #f7f7f9; color: #222; }}
  h1 {{ color: #2c3e50; }}
  .summary-grid {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
  .card {{ background: white; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 140px; }}
  .card .number {{ font-size: 28px; font-weight: bold; }}
  .card .label {{ color: #666; font-size: 13px; text-transform: uppercase; }}
  table {{ width: 100%; border-collapse: collapse; background: white; margin-top: 10px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 14px; }}
  th {{ background: #2c3e50; color: white; }}
  section {{ margin-bottom: 30px; }}
</style>
</head>
<body>
  <h1>Desktop Automation Report</h1>
  <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

  <div class="summary-grid">
    <div class="card"><div class="number">{len(moved)}</div><div class="label">Moved</div></div>
    <div class="card"><div class="number">{len(archived)}</div><div class="label">Archived</div></div>
    <div class="card"><div class="number">{len(duplicates)}</div><div class="label">Duplicates</div></div>
    <div class="card"><div class="number">{len(errors)}</div><div class="label">Errors</div></div>
    <div class="card"><div class="number">{format_bytes(space_freed_bytes)}</div><div class="label">Space Freed</div></div>
  </div>

  <section>
    <h2>Moved Files</h2>
    <table><tr><th>Filename</th><th>Destination</th><th>Detail</th></tr>{rows_html(moved)}</table>
  </section>

  <section>
    <h2>Archived Files</h2>
    <table><tr><th>Filename</th><th>Destination</th><th>Detail</th></tr>{rows_html(archived)}</table>
  </section>

  <section>
    <h2>Duplicates Found</h2>
    <table><tr><th>Filename</th><th>Destination</th><th>Detail</th></tr>{rows_html(duplicates)}</table>
  </section>

  <section>
    <h2>Errors</h2>
    <table><tr><th>Filename</th><th>Destination</th><th>Detail</th></tr>{rows_html(errors)}</table>
  </section>
</body>
</html>"""

    report_path.write_text(html, encoding="utf-8")
    return report_path
