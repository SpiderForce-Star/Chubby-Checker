#!/usr/bin/env python3
"""Chubby Checker – CLI"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from pathlib import Path
from typing import Tuple, Optional

from chubby_checker.auth import require_access, PRODUCT_NAME
from chubby_checker.branding import find_logo, COMPANY_NAME
from chubby_checker.automation import run_job, extract_job_number
from chubby_checker.errors import (
    ChubbyCheckerError,
    MissingFileError,
    MissingDirectoryError,
    EmptyInputError,
    require_shippers,
    optional_pdf,
    format_missing_help,
)

console = Console()


@click.command()
@click.option(
    "--shipper",
    "shippers",
    multiple=True,
    required=True,
    type=click.Path(),  # validate ourselves for clearer errors
    help="Path to Complete Shipper PDF (repeat for multi-phase jobs)",
)
@click.option(
    "--drawings",
    required=False,
    default=None,
    type=click.Path(),
    help="Path to Final Drawings PDF",
)
@click.option("--job", default=None, help="Job number (auto-detected from filenames if omitted)")
@click.option(
    "--output-dir",
    default="./reports",
    type=click.Path(),
    help="Directory for the PDF report (default: ./reports)",
)
@click.option(
    "--no-pdf",
    is_flag=True,
    default=False,
    help="Skip PDF report generation (not recommended)",
)
@click.option(
    "--no-watermark",
    is_flag=True,
    default=False,
    help="Deprecated: watermarks are off by default (flag kept for compatibility)",
)
@click.option(
    "--watermark",
    "enable_watermark",
    is_flag=True,
    default=False,
    help="Opt-in only: add page numbers (no diagonal text watermarks)",
)
@click.option(
    "--logo",
    default=None,
    type=click.Path(),
    help="Override path to Ascent logo image for the PDF report",
)
@click.option(
    "--access-code",
    default=None,
    help="Access code / license key (or set env). Prompts if omitted.",
)
def main(
    shippers: Tuple[str, ...],
    drawings: Optional[str] = None,
    job: Optional[str] = None,
    output_dir: str = "./reports",
    no_pdf: bool = False,
    no_watermark: bool = False,
    enable_watermark: bool = False,
    logo: Optional[str] = None,
    access_code: Optional[str] = None,
):
    """Chubby Checker — verify Complete Shippers against Final Drawings."""

    require_access(provided=access_code)

    console.print(Panel.fit(
        f"[bold green]{PRODUCT_NAME}[/bold green]\n"
        f"[dim]{COMPANY_NAME}[/dim]\n"
        "PEMB Shipper vs Drawings Verifier  •  Automated PDF Report",
        border_style="green",
    ))

    # ---- Validate inputs early with clear messages ----
    try:
        shipper_paths = require_shippers(shippers)
    except (MissingFileError, EmptyInputError, ChubbyCheckerError) as exc:
        console.print(f"[bold red]Missing shipper file(s)[/bold red]")
        console.print(f"[red]{exc}[/red]")
        console.print(format_missing_help("shipper", shippers[0] if shippers else ""))
        raise SystemExit(1)

    try:
        drawings_path = optional_pdf(drawings, role="drawings PDF") if drawings else None
    except (MissingFileError, ChubbyCheckerError) as exc:
        console.print(f"[bold red]Missing drawings file[/bold red]")
        console.print(f"[red]{exc}[/red]")
        console.print(format_missing_help("drawings", drawings or ""))
        raise SystemExit(1)

    logo_path = None
    if logo:
        lp = Path(logo).expanduser()
        if not lp.is_file():
            console.print(f"[bold red]Missing logo file[/bold red]: {lp}")
            console.print(format_missing_help("logo", lp))
            raise SystemExit(1)
        logo_path = lp.resolve()
    else:
        logo_path = find_logo()

    if logo_path:
        console.print(f"[dim]Logo: {logo_path}[/dim]")
    else:
        console.print("[dim]Logo: not found (report will run without header logo)[/dim]")

    job_number = job or extract_job_number(*shipper_paths, drawings_path or Path())
    if job_number:
        console.print(f"[bold]Job:[/bold] {job_number}")
    else:
        console.print("[yellow]Warning: could not detect job number from filenames; using UNKNOWN[/yellow]")

    if no_pdf:
        from chubby_checker.automation import _parse_shippers, _parse_drawings
        from chubby_checker.rules.engine import DiscrepancyEngine

        try:
            console.print("\n[cyan]Running check without PDF…[/cyan]")
            shipper_data = _parse_shippers(shipper_paths)
            drawings_data = _parse_drawings(drawings_path)
        except (MissingFileError, ChubbyCheckerError) as exc:
            console.print(f"[red]{exc}[/red]")
            raise SystemExit(1)

        engine = DiscrepancyEngine(shipper_data=shipper_data, drawings_data=drawings_data)
        findings = engine.run()
        critical = sum(1 for f in findings if getattr(f, "severity", "").upper() == "CRITICAL")
        warning = sum(1 for f in findings if getattr(f, "severity", "").upper() == "WARNING")
        info = sum(1 for f in findings if getattr(f, "severity", "").upper() == "INFO")
        table = Table(title="Discrepancy Summary")
        table.add_column("Severity", style="bold")
        table.add_column("Count", justify="right")
        table.add_row("[bold red]CRITICAL[/bold red]", str(critical))
        table.add_row("[yellow]WARNING[/yellow]", str(warning))
        table.add_row("[cyan]INFO[/cyan]", str(info))
        console.print(table)
        console.print("\n" + engine.report())
        console.print("\n[dim]PDF report skipped (--no-pdf).[/dim]")
        return

    console.print("\n[cyan]Running automated check + PDF report…[/cyan]")
    result = run_job(
        shippers=shipper_paths,
        drawings=drawings_path,
        job_number=job_number,
        output_dir=output_dir,
        watermark=bool(enable_watermark) and not no_watermark,
        logo_path=logo_path,
    )

    if not result.success:
        console.print(f"[bold red]Failed:[/bold red] {result.error}")
        raise SystemExit(1)

    table = Table(title="Discrepancy Summary")
    table.add_column("Severity", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("[bold red]CRITICAL[/bold red]", str(result.critical))
    table.add_row("[yellow]WARNING[/yellow]", str(result.warning))
    table.add_row("[cyan]INFO[/cyan]", str(result.info))
    console.print(table)

    console.print(f"\n   [bold green]Report saved:[/bold green] {result.report_path}")
    if result.critical or result.warning:
        console.print("[bold red]Status: ERRORS FOUND — review required before release.[/bold red]")
    else:
        console.print("[bold green]Status: NO ERRORS[/bold green]")


if __name__ == "__main__":
    main()
