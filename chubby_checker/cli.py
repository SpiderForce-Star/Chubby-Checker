#!/usr/bin/env python3
"""Chubby-Checker CLI – supports single or multi-phase shippers"""

import click
from rich.console import Console
from rich.panel import Panel
from pathlib import Path

from chubby_checker.parsers.shipper_parser import ShipperParser
from chubby_checker.parsers.drawings_parser import DrawingsParser
from chubby_checker.parsers.multi_phase import MultiPhaseShipper
from chubby_checker.rules.engine import DiscrepancyEngine

console = Console()

@click.command()
@click.option(
    "--shipper",
    required=True,
    multiple=True,
    type=click.Path(exists=True),
    help="Path to Complete Shipper PDF (can be specified multiple times for multi-phase jobs)",
)
@click.option("--drawings", required=False, type=click.Path(exists=True), help="Path to Final Drawings PDF")
def main(shipper, drawings: str = None):
    console.print(Panel.fit("[bold green]Chubby-Checker v0.2[/bold green]\nPEMB Shipper vs Drawings Verifier\n(Multi-phase support)", border_style="green"))

    shipper_paths = list(shipper)

    # ---- Shipper(s) ----
    if len(shipper_paths) == 1:
        console.print(f"\n[cyan]Parsing single shipper:[/cyan] {shipper_paths[0]}")
        parser = ShipperParser(shipper_paths[0])
        result = parser.parse()
        # Normalize to rich dict
        if isinstance(result, dict) and "categories" in result:
            shipper_data = result
        else:
            shipper_data = {
                "categories": result,
                "ss_accessories": parser.get_ss_accessories(),
                "panel_coverage": {},
                "summary": None,
            }
    else:
        console.print(f"\n[cyan]Parsing {len(shipper_paths)} phase shippers...[/cyan]")
        multi = MultiPhaseShipper(shipper_paths)
        shipper_data = multi.parse()
        console.print(multi.get_phase_summary())

    # Summary output
    summary = shipper_data.get("summary")
    if summary:
        console.print(f"  Job: {getattr(summary, 'job_number', '')} {getattr(summary, 'phase', '')}")
        console.print(f"  Total Weight: {getattr(summary, 'total_weight', 0):,.1f} lbs")

    coverage = shipper_data.get("panel_coverage", {})
    if coverage:
        console.print(f"  Panel coverage: {coverage}")

    accessories = shipper_data.get("ss_accessories", {})
    if any(v > 0 for v in accessories.values()):
        console.print(f"  Sliding clips: {accessories.get('sliding_clips', 0):,}")
        console.print(f"  Thermal blocks: {accessories.get('thermal_blocks', 0):,}")
        console.print(f"  24\" backup plates: {accessories.get('backup_plates_24', 0):,}")

    # ---- Drawings ----
    drawings_data = {}
    if drawings:
        console.print(f"\n[cyan]Parsing drawings:[/cyan] {drawings}")
        drawings_parser = DrawingsParser(drawings)
        drawings_data = drawings_parser.parse()

        drawings_data["mark_quantity_map"] = drawings_parser.get_mark_quantity_map()
        notes = drawings_parser.get_notes()
        drawings_data["has_crane"] = notes.get("has_crane", False)
        drawings_data["has_mezzanine"] = notes.get("has_mezzanine", False)

        total_marks = len(drawings_data.get("mark_quantity_map", {}))
        console.print(f"  Extracted {total_marks} unique marks from Member Tables")
        if notes.get("has_crane"):
            console.print("  [yellow]Crane / runway system detected in drawings[/yellow]")
        if notes.get("has_mezzanine"):
            console.print("  [yellow]Mezzanine detected in drawings[/yellow]")

    # ---- Engine ----
    console.print("\n[cyan]Running discrepancy engine...[/cyan]")
    engine = DiscrepancyEngine(shipper_data, drawings_data)
    findings = engine.run()

    report = engine.report()
    console.print("\n" + report)

    if findings:
        console.print(f"\n[yellow]Found {len(findings)} item(s).[/yellow]")
    else:
        console.print("\n[green]No discrepancies flagged by current rules.[/green]")

if __name__ == "__main__":
    main()
