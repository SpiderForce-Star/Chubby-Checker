#!/usr/bin/env python3
"""Chubby-Checker CLI – Ascent Buildings Shipper Verifier"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from pathlib import Path
from typing import Tuple
from datetime import datetime

from chubby_checker.parsers.shipper_parser import ShipperParser
from chubby_checker.parsers.drawings_parser import DrawingsParser
from chubby_checker.rules.engine import DiscrepancyEngine
from chubby_checker.report.pdf_report import generate_pdf_report

console = Console()


def _try_multi_phase(shippers):
    """Use multi-phase aggregator when available and multiple files given."""
    if len(shippers) <= 1:
        return None
    try:
        from chubby_checker.parsers.multi_phase import MultiPhaseShipper
        return MultiPhaseShipper
    except ImportError:
        try:
            from chubby_checker.parsers.multi_shipper import MultiShipperAggregator
            return MultiShipperAggregator
        except ImportError:
            return None


@click.command()
@click.option(
    "--shipper",
    "shippers",
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help="Path to Complete Shipper PDF (repeat for multi-phase jobs)",
)
@click.option(
    "--drawings",
    required=False,
    type=click.Path(exists=True),
    help="Path to Final Drawings PDF",
)
@click.option("--job", default=None, help="Job number (used in report filename)")
@click.option(
    "--output-dir",
    default=".",
    type=click.Path(),
    help="Directory for the PDF report (default: current directory)",
)
@click.option(
    "--no-pdf",
    is_flag=True,
    default=False,
    help="Skip PDF report generation",
)
def main(
    shippers: Tuple[str, ...],
    drawings: str = None,
    job: str = None,
    output_dir: str = ".",
    no_pdf: bool = False,
):
    """Run Chubby Checker and produce a PDF verification report."""
    console.print(Panel.fit(
        "[bold green]Chubby-Checker[/bold green]\n"
        "PEMB Shipper vs Drawings Verifier  •  PDF Report",
        border_style="green",
    ))

    check_date = datetime.now()
    if job:
        console.print(f"[bold]Job:[/bold] {job}")

    # ------------------------------------------------------------------
    # 1. Parse Shipper(s)
    # ------------------------------------------------------------------
    MultiCls = _try_multi_phase(shippers)

    if len(shippers) > 1 and MultiCls is not None:
        console.print(f"\n[cyan]1. Parsing {len(shippers)} phase shippers…[/cyan]")
        aggregator = MultiCls(list(shippers))
        shipper_data = aggregator.parse() if hasattr(aggregator, "parse") else {}
        if not shipper_data and hasattr(aggregator, "as_shipper_data"):
            shipper_data = aggregator.as_shipper_data()
    else:
        console.print(f"\n[cyan]1. Parsing shipper:[/cyan] {shippers[0]}")
        parser = ShipperParser(shippers[0])
        pieces = parser.parse()
        shipper_data = {
            "categories": pieces,
            "ss_accessories": parser.get_ss_accessories() if hasattr(parser, "get_ss_accessories") else {},
            "summary_weights": parser.get_summary_weights() if hasattr(parser, "get_summary_weights") else {},
            "panel_coverage": {},
            "mark_qty": {},
        }
        for plist in pieces.values():
            for p in plist:
                shipper_data["mark_qty"][p.mark] = shipper_data["mark_qty"].get(p.mark, 0) + p.quantity

        # If additional shippers were passed but no multi-phase module, parse & merge simply
        for extra in shippers[1:]:
            console.print(f"   + merging {extra}")
            ep = ShipperParser(extra)
            epieces = ep.parse()
            for cat, plist in epieces.items():
                shipper_data["categories"].setdefault(cat, []).extend(plist)
                for p in plist:
                    shipper_data["mark_qty"][p.mark] = shipper_data["mark_qty"].get(p.mark, 0) + p.quantity
            if hasattr(ep, "get_ss_accessories"):
                for k, v in ep.get_ss_accessories().items():
                    shipper_data["ss_accessories"][k] = shipper_data["ss_accessories"].get(k, 0) + v

    accessories = shipper_data.get("ss_accessories", {})
    if any(accessories.values()):
        console.print(f"   Sliding clips : {accessories.get('sliding_clips', 0):,}")
        console.print(f"   Thermal blocks: {accessories.get('thermal_blocks', 0):,}")

    console.print(f"   Unique marks  : {len(shipper_data.get('mark_qty', {}))}")

    # ------------------------------------------------------------------
    # 2. Parse Drawings
    # ------------------------------------------------------------------
    drawings_data = {}
    if drawings:
        console.print(f"\n[cyan]2. Parsing drawings:[/cyan] {drawings}")
        dparser = DrawingsParser(drawings)
        member_tables = dparser.parse()
        drawings_data = {
            "member_tables": member_tables,
            "mark_quantity_map": dparser.get_mark_quantity_map() if hasattr(dparser, "get_mark_quantity_map") else {},
            "notes": dparser.get_notes() if hasattr(dparser, "get_notes") else {},
        }
        notes = drawings_data.get("notes") or {}
        if isinstance(notes, dict):
            if notes.get("has_mezzanine"):
                drawings_data["has_mezzanine"] = True
                console.print("   [yellow]Mezzanine detected[/yellow]")
            if notes.get("has_crane"):
                drawings_data["has_crane"] = True
                console.print("   [yellow]Crane / runway referenced[/yellow]")
        console.print(f"   Member marks  : {len(drawings_data.get('mark_quantity_map', {}))}")
    else:
        console.print("\n[dim]2. No drawings supplied.[/dim]")

    # ------------------------------------------------------------------
    # 3. Run engine
    # ------------------------------------------------------------------
    console.print("\n[cyan]3. Running discrepancy engine…[/cyan]")
    engine = DiscrepancyEngine(shipper_data=shipper_data, drawings_data=drawings_data)
    findings = engine.run()

    # Console summary
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

    # ------------------------------------------------------------------
    # 4. PDF Report
    # ------------------------------------------------------------------
    if not no_pdf:
        console.print("\n[cyan]4. Generating PDF report…[/cyan]")
        pdf_path = generate_pdf_report(
            discrepancies=findings,
            job_number=job,
            output_dir=output_dir,
            check_date=check_date,
            shipper_files=list(shippers),
            drawings_file=drawings,
        )
        console.print(f"   [bold green]Report saved:[/bold green] {pdf_path}")

        if critical or warning:
            console.print("[bold red]Status: ERRORS FOUND — review required before release.[/bold red]")
        else:
            console.print("[bold green]Status: NO ERRORS[/bold green]")
    else:
        console.print("\n[dim]PDF report skipped (--no-pdf).[/dim]")


if __name__ == "__main__":
    main()
