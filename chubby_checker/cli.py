#!/usr/bin/env python3
"""Chubby-Checker CLI – Ascent Buildings Shipper Verifier"""

import click
from rich.console import Console
from rich.panel import Panel
from pathlib import Path

from chubby_checker.parsers.shipper_parser import ShipperParser
from chubby_checker.parsers.drawings_parser import DrawingsParser
from chubby_checker.rules.engine import DiscrepancyEngine

console = Console()


@click.command()
@click.option("--shipper", required=True, type=click.Path(exists=True), help="Path to Complete Shipper PDF")
@click.option("--drawings", required=False, type=click.Path(exists=True), help="Path to Final Drawings PDF")
def main(shipper: str, drawings: str = None):
    console.print(Panel.fit(
        "[bold green]Chubby-Checker v0.3[/bold green]\nPEMB Shipper vs Drawings Verifier",
        border_style="green"
    ))

    # ------------------------------------------------------------------
    # 1. Parse Shipper
    # ------------------------------------------------------------------
    console.print(f"\n[cyan]1. Parsing shipper:[/cyan] {shipper}")
    shipper_parser = ShipperParser(shipper)
    shipper_pieces = shipper_parser.parse()

    # Build a consistent data dict for the engine
    shipper_data = {
        "categories": shipper_pieces,
        "ss_accessories": shipper_parser.get_ss_accessories(),
        "summary_weights": shipper_parser.get_summary_weights(),
        "panel_coverage": {},   # can be enriched later
    }

    # Quick summary
    accessories = shipper_data["ss_accessories"]
    if any(accessories.values()):
        console.print(f"   Sliding clips     : {accessories.get('sliding_clips', 0):,}")
        console.print(f"   Thermal blocks    : {accessories.get('thermal_blocks', 0):,}")
        console.print(f"   24\" backup plates : {accessories.get('backup_plates_24', 0):,}")

    # Build shipper mark → qty map
    shipper_mark_qty = {}
    for pieces in shipper_pieces.values():
        for p in pieces:
            shipper_mark_qty[p.mark] = shipper_mark_qty.get(p.mark, 0) + p.quantity

    console.print(f"   Unique marks found: {len(shipper_mark_qty)}")

    # ------------------------------------------------------------------
    # 2. Parse Drawings (optional but recommended)
    # ------------------------------------------------------------------
    drawings_mark_qty = {}
    drawings_data = {}

    if drawings:
        console.print(f"\n[cyan]2. Parsing drawings:[/cyan] {drawings}")
        drawings_parser = DrawingsParser(drawings)
        member_tables = drawings_parser.parse()
        drawings_data = {
            "member_tables": member_tables,
            "notes": drawings_parser.get_notes(),
        }
        drawings_mark_qty = drawings_parser.get_mark_quantity_map()
        console.print(f"   Member Table marks: {len(drawings_mark_qty)}")
        notes = drawings_parser.get_notes()
        if notes.get("has_mezzanine"):
            console.print("   [yellow]Mezzanine detected in drawings[/yellow]")
        if notes.get("has_crane"):
            console.print("   [yellow]Crane / runway referenced in drawings[/yellow]")
    else:
        console.print("\n[dim]2. No drawings supplied – mark-by-mark comparison will be limited.[/dim]")

    # ------------------------------------------------------------------
    # 3. Run Discrepancy Engine
    # ------------------------------------------------------------------
    console.print("\n[cyan]3. Running discrepancy engine (including mark-by-mark)…[/cyan]")
    engine = DiscrepancyEngine(
        shipper_data=shipper_data,
        drawings_data=drawings_data,
        drawings_mark_qty=drawings_mark_qty,
        shipper_mark_qty=shipper_mark_qty,
    )
    findings = engine.run()

    # ------------------------------------------------------------------
    # 4. Report
    # ------------------------------------------------------------------
    report = engine.report()
    console.print("\n" + report)

    if findings:
        critical = sum(1 for f in findings if f.severity == "CRITICAL")
        warning = sum(1 for f in findings if f.severity == "WARNING")
        console.print(f"\n[yellow]Found {len(findings)} item(s)"
                      f" ({critical} critical, {warning} warning).[/yellow]")
    else:
        console.print("\n[green]No discrepancies flagged by current rules.[/green]")


if __name__ == "__main__":
    main()
