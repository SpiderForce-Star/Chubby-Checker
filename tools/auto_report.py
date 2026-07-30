#!/usr/bin/env python3
"""
Automated batch PDF report generation for Chubby Checker.

Examples:
  python tools/auto_report.py --jobs-dir ./jobs --output-dir ./reports
  python tools/auto_report.py --jobs-dir ./jobs --only 25-13168
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

    from chubby_checker.auth import require_access, PRODUCT_NAME
    from chubby_checker.branding import COMPANY_NAME, find_logo
    from chubby_checker.automation import discover_jobs, run_batch
    from chubby_checker.errors import (
        ChubbyCheckerError,
        MissingDirectoryError,
        MissingFileError,
        format_missing_help,
    )

    console = Console()

    parser = argparse.ArgumentParser(
        description=f"{PRODUCT_NAME} — automated PDF report generation",
    )
    parser.add_argument("--jobs-dir", required=True, type=Path,
                        help="Folder containing shipper/drawings PDFs (or job subfolders)")
    parser.add_argument("--output-dir", default=Path("./reports"), type=Path,
                        help="Where to write CC_Checked_*.pdf reports (default: ./reports)")
    parser.add_argument("--only", action="append", default=[],
                        help="Limit to this job number (repeatable)")
    parser.add_argument("--no-recursive", action="store_true",
                        help="Do not scan subfolders")
    parser.add_argument("--no-watermark", action="store_true",
                        help="Deprecated: watermarks are off by default")
    parser.add_argument("--watermark", action="store_true",
                        help="Opt-in only: page numbers (no diagonal text watermarks)")
    parser.add_argument("--logo", type=Path, default=None,
                        help="Override Ascent logo path")
    parser.add_argument("--access-code", default=None,
                        help="License key or legacy access code")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only list discovered jobs; do not run checks or write PDFs")
    args = parser.parse_args(argv)

    try:
        require_access(provided=args.access_code)
    except SystemExit:
        raise
    except Exception as exc:
        console.print(f"[red]Access / license error:[/red] {exc}")
        return 1

    console.print(Panel.fit(
        f"[bold green]{PRODUCT_NAME}[/bold green]\n"
        f"[dim]{COMPANY_NAME}[/dim]\n"
        "Automated PDF Report Generation",
        border_style="green",
    ))

    jobs_dir = args.jobs_dir.expanduser()
    if not jobs_dir.exists():
        console.print(f"[red]Missing jobs directory:[/red] {jobs_dir}")
        console.print(format_missing_help("jobs directory", jobs_dir))
        return 1
    if not jobs_dir.is_dir():
        console.print(f"[red]Not a directory:[/red] {jobs_dir}")
        return 1

    if args.logo is not None:
        logo = args.logo.expanduser()
        if not logo.is_file():
            console.print(f"[red]Missing logo file:[/red] {logo}")
            console.print(format_missing_help("logo", logo))
            return 1
    else:
        logo = find_logo()

    try:
        bundles = discover_jobs(jobs_dir, recursive=not args.no_recursive)
    except (MissingDirectoryError, MissingFileError, ChubbyCheckerError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 1
    except Exception as exc:
        console.print(f"[red]Discovery failed:[/red] {exc}")
        return 1

    if args.only:
        allow = set(args.only)
        bundles = [b for b in bundles if b.job_number in allow]
        if not bundles:
            console.print(
                f"[red]No jobs matched --only filter:[/red] {', '.join(sorted(allow))}"
            )
            return 1

    # Flag jobs missing drawings (still runnable, but warn)
    table = Table(title="Discovered Jobs")
    table.add_column("Job")
    table.add_column("Shippers", justify="right")
    table.add_column("Drawings")
    table.add_column("Notes")
    for b in bundles:
        notes = []
        if not b.drawings:
            notes.append("no drawings PDF")
        missing_ship = [str(p) for p in b.shippers if not p.is_file()]
        if missing_ship:
            notes.append("shipper path missing on disk")
        table.add_row(
            b.job_number,
            str(len(b.shippers)),
            b.drawings.name if b.drawings else "—",
            "; ".join(notes) or "",
        )
    console.print(table)

    if args.dry_run:
        console.print("[dim]Dry run only — no reports written.[/dim]")
        return 0

    console.print(f"\n[cyan]Generating PDF reports → {args.output_dir.expanduser().resolve()}[/cyan]")
    try:
        results = run_batch(
            jobs_dir=jobs_dir,
            output_dir=args.output_dir,
            recursive=not args.no_recursive,
            watermark=bool(args.watermark) and not args.no_watermark,
            logo_path=logo,
            only_jobs=args.only or None,
        )
    except (MissingDirectoryError, MissingFileError, ChubbyCheckerError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    summary = Table(title="Batch Results")
    summary.add_column("Job")
    summary.add_column("Status")
    summary.add_column("CRIT", justify="right")
    summary.add_column("WARN", justify="right")
    summary.add_column("Report / Error")

    failures = 0
    for r in results:
        if not r.success:
            failures += 1
            summary.add_row(r.job_number, "[red]FAIL[/red]", "—", "—", r.error or "unknown error")
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
    if failures:
        console.print(
            "[yellow]Failed jobs usually mean a missing/unreadable PDF or parse error. "
            "Re-check paths listed above.[/yellow]"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
