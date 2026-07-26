import click
from rich.console import Console

console = Console()

@click.command()
@click.option("--drawings", required=True, type=click.Path(exists=True), help="Path to Final Drawings PDF")
@click.option("--shipper", required=True, type=click.Path(exists=True), help="Path to Complete Shipper PDF")
def main(drawings: str, shipper: str):
    console.print("[bold green]Chubby Checker v0.1[/bold green]")
    console.print(f"Drawings: {drawings}")
    console.print(f"Shipper : {shipper}")
    console.print("\n[yellow]Early scaffold - parsers and rules being calibrated on real Ascent jobs.[/yellow]")

if __name__ == "__main__":
    main()
