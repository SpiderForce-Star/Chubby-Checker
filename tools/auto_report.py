#!/usr/bin/env python3
"""
Automated batch PDF report generation for Ascent Shipper Checker.

Examples:
  # Process every job found under ./jobs into ./reports
  python tools/auto_report.py --jobs-dir ./jobs --output-dir ./reports

  # Single job folder
  python tools/auto_report.py --jobs-dir ./jobs/25-13168 --output-dir ./reports

  # Only specific jobs
  python tools/auto_report.py --jobs-dir ./jobs --only 25-13168 --only 25-13059
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    from chubby_checker.auth import require_access, PRODUCT_NAME, CODENAME
    from chubby_checker.branding import COMPANY_NAME, find_logo
    from chubby_checker.automation import discover_jobs, run_batch, extract_job_number

    console = Console()

    parser = argparse.ArgumentParser(
        description=f"{PRODUCT_NAME} — automated PDF report generation",
    )
    parser.add_argument(
        "--jobs-dir",
        required=True,
        type=Path,
        help="Folder containing shipper/drawings PDFs (or job subfolders)",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("./reports"),
        type=Path,
        help="Where to write CC_Checked_*.pdf reports (default: ./reports)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Limit to this job number (repeatable)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not scan subfolders",
    )
    parser.add_argument(
        "--no-watermark",
        action="store_true",
        help="Disable PDF watermark / corner logo",
    )
    parser.add_argument(
        "--logo",
        type=Path,
        default=None,
        help="Override Ascent logo path",
    )
    parser.add_argument(
        "--access-code",
        default=None,
        help="License key or legacy access code",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list discovered jobs; do not run checks or write PDFs",
    )
    args = parser.parse_args(argv)

    require_access(provided=args.access_code)

    console.print(Panel.fit(
        f"[bold green]{PRODUCT_NAME}[/bold green]\n"
        f"[dim]codename {CODENAME}  ·  {COMPANY_NAME}[/dim]\n"
        "Automated PDF Report Generation",
        border_style="green",
    ))

    jobs_dir = args.jobs_dir
    if not jobs_dir.is_dir():
        console.print(f"[red]Jobs directory not found:[/red] {jobs_dir}")
        return 1

    try:
        bundles = discover_jobs(jobs_dir, recursive=not args.no_recursive)
    except Exception as exc:
        console.print(f"[red]Discovery failed:[/red] {exc}")
        return 1

    if args.only:
        allow = set(args.only)
        bundles = [b for b in bundles if b.job_number in allow]

    if not bundles:
        console.print("[yellow]No jobs discovered. Check folder contents and filenames.[/yellow]")
        console.print("Expected PDFs containing job numbers like 25-13168 and keywords")
        console.print("  shipper: Complete Shipper, BOM, PH1…")
        console.print("  drawings: FINAL, Erection, Drawings")
        return 1

    table = Table(title="Discovered Jobs")
    table.add_column("Job")
    table.add_column("Shippers", justify="right")
    table.add_column("Drawings")
    for b in bundles:
        table.add_row(
            b.job_number,
            str(len(b.shippers)),
            b.drawings.name if b.drawings else "—",
        )
    console.print(table)

    if args.dry_run:
        console.print("[dim]Dry run only — no reports written.[/dim]")
        return 0

    console.print(f"\n[cyan]Generating PDF reports → {args.output_dir.resolve()}[/cyan]")
    results = run_batch(
        jobs_dir=jobs_dir,
        output_dir=args.output_dir,
        recursive=not args.no_recursive,
        watermark=not args.no_watermark,
        logo_path=args.logo or find_logo(),
        only_jobs=args.only or None,
    )

    summary = Table(title="Batch Results")
    summary.add_column("Job")
    summary.add_column("Status")
    summary.add_column("CRIT", justify="right")
    summary.add_column("WARN", justify="right")
    summary.add_column("Report")

    failures = 0
    for r in results:
        if not r.success:
            failures += 1
            summary.add_row(r.job_number, "[red]FAIL[/red]", "—", "—", r.error or "")
            continue
        status = "[red]ERRORS[/red]" if (r.critical or r.warning) else "[green]NO ERRORS[/green]"
        summary.add_row(
            r.job_number,
            status,
            str(r.critical),
            str(r.warning),
            str(r.report_path.name) if r.report_path else "—",
        )
    console.print(summary)

    console.print(
        f"\n[bold]Done.[/bold] {len(results) - failures}/{len(results)} jobs produced reports."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
