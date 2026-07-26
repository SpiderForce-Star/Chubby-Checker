#!/usr/bin/env python3
"""Chubby-Checker CLI"""

import click
from rich.console import Console
from rich.panel import Panel
from pathlib import Path

from chubby_checker.parsers.shipper_parser import ShipperParser
from chubby_checker.rules.engine import DiscrepancyEngine

console = Console()

@click.command()
@click.option("--shipper", required=True, type=click.Path(exists=True), help="Path to Complete Shipper PDF")
@click.option("--drawings", required=False, type=click.Path(exists=True), help="Path to Final Drawings PDF (optional for now)")
def main(shipper: str, drawings: str = None):
    console.print(Panel.fit("[bold green]Chubby-Checker v0.1[/bold green]\nPEMB Shipper vs Drawings Verifier", border_style="green"))

    console.print(f"\n[cyan]Parsing shipper:[/cyan] {shipper}")
    parser = ShipperParser(shipper)
    shipper_data = parser.parse()

    # Quick summary
    summary = shipper_data.get("summary")
    if summary:
        console.print(f"  Job: {summary.job_number} {summary.phase}")
        console.print(f"  Total Weight: {summary.total_weight:,.1f} lbs")

    coverage = shipper_data.get("panel_coverage", {})
    if coverage:
        console.print(f"  Panel coverage: {coverage}")

    accessories = shipper_data.get("ss_accessories", {})
    if any(accessories.values()):
        console.print(f"  Sliding clips: {accessories.get('sliding_clips', 0):,}")
        console.print(f"  Thermal blocks: {accessories.get('thermal_blocks', 0):,}")
        console.print(f"  24\" backup plates: {accessories.get('backup_plates_24', 0):,}")

    console.print("\n[cyan]Running discrepancy engine...[/cyan]")
    engine = DiscrepancyEngine(shipper_data)
    findings = engine.run()

    report = engine.report()
    console.print("\n" + report)

    if findings:
        console.print(f"\n[yellow]Found {len(findings)} item(s).[/yellow]")
    else:
        console.print("\n[green]No discrepancies flagged by current rules.[/green]")

if __name__ == "__main__":
    main()
