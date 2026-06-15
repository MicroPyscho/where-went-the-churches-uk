"""
main.py — CLI runner for the UK Church Conversion Pipeline

Usage:
  python main.py                    # Run all sources
  python main.py --sources wikidata osm   # Run specific sources only
  python main.py --skip-geocode     # Skip geocoding (faster dev runs)
  python main.py --dry-run          # Extract only, don't write outputs
"""

import logging
import sys
import time
import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import print as rprint
import pandas as pd

console = Console()
app = typer.Typer(help="UK Church Conversion Data Pipeline")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.FileHandler("pipeline.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def print_header():
    console.print(Panel.fit(
        "[bold white]UK Church Conversion Research Pipeline[/bold white]\n"
        "[dim]Tracking religious landscape change across England, Wales, Scotland & NI[/dim]",
        border_style="blue",
    ))


def print_source_results(source_name: str, df: pd.DataFrame):
    if df.empty:
        console.print(f"  [yellow]⚠ {source_name}: 0 records[/yellow]")
        return

    # Count by conversion type
    type_counts = df["conversion_type"].value_counts().to_dict()
    type_str = ", ".join(f"{k}: {v}" for k, v in list(type_counts.items())[:4])
    console.print(
        f"  [green]✓[/green] [bold]{source_name}[/bold]: "
        f"[cyan]{len(df):,}[/cyan] records  |  {type_str}"
    )


def print_final_summary(df: pd.DataFrame):
    console.print("\n")
    console.print(Panel.fit("[bold green]Pipeline Complete[/bold green]", border_style="green"))

    table = Table(title="Conversion Type Breakdown", show_lines=True)
    table.add_column("Type",          style="bold")
    table.add_column("Count",         justify="right", style="cyan")
    table.add_column("% of Total",    justify="right", style="yellow")
    table.add_column("With Coords",   justify="right")
    table.add_column("With Year",     justify="right")

    total = len(df)
    for ct in df["conversion_type"].value_counts().index:
        subset = df[df["conversion_type"] == ct]
        count     = len(subset)
        pct       = 100 * count / total
        w_coords  = subset["latitude"].notna().sum()
        w_year    = subset["year_converted"].notna().sum()
        table.add_row(
            ct, f"{count:,}", f"{pct:.1f}%",
            f"{w_coords:,}", f"{w_year:,}"
        )
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total:,}[/bold]", "100%", "", "")
    console.print(table)

    # Nation summary
    nation_table = Table(title="By Nation")
    nation_table.add_column("Nation")
    nation_table.add_column("Count", justify="right", style="cyan")
    for nation, count in df["nation"].value_counts().items():
        nation_table.add_row(str(nation), str(count))
    nation_table.add_row("[dim]Unknown[/dim]", str(df["nation"].isna().sum()))
    console.print(nation_table)


@app.command()
def run(
    sources: Optional[list[str]] = typer.Option(
        None, "--sources", "-s",
        help="Sources to run: wikidata, osm, historic_england, charity_commission. Default: all."
    ),
    skip_geocode: bool = typer.Option(
        False, "--skip-geocode",
        help="Skip geocoding step (faster for dev/testing)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Extract data but do not write output files"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Debug logging"
    ),
    output_dir: str = typer.Option(
        "data/output",
        "--output-dir",
        help="Directory to write output files"
    ),
):
    """
    Run the UK Church Conversion data pipeline.

    Pulls data from Wikidata, OpenStreetMap, Historic England, and the
    Charity Commission, transforms and deduplicates, then writes CSV,
    PostgreSQL, and Excel outputs.
    """
    setup_logging(verbose)
    print_header()
    start_time = time.time()

    # Determine which sources to run
    all_sources = ["wikidata", "osm", "historic_england", "charity_commission"]
    run_sources = sources if sources else all_sources

    console.print(f"\n[bold]Sources:[/bold] {', '.join(run_sources)}")
    console.print(f"[bold]Skip geocode:[/bold] {skip_geocode}")
    console.print(f"[bold]Dry run:[/bold] {dry_run}\n")

    # ── EXTRACTION ────────────────────────────────────────────────────────────
    console.rule("[bold blue]Stage 1: Extraction[/bold blue]")
    source_dfs = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        if "wikidata" in run_sources:
            task = progress.add_task("Wikidata SPARQL...", total=None)
            try:
                from extractors.wikidata_extractor import extract as wikidata_extract
                df_wd = wikidata_extract()
                source_dfs.append(df_wd)
                print_source_results("Wikidata", df_wd)
                df_wd.to_csv("data/raw/wikidata_raw.csv", index=False)
            except Exception as e:
                console.print(f"  [red]✗ Wikidata failed: {e}[/red]")
            progress.remove_task(task)

        if "osm" in run_sources:
            task = progress.add_task("OpenStreetMap Overpass...", total=None)
            try:
                from extractors.osm_extractor import extract as osm_extract
                df_osm = osm_extract()
                source_dfs.append(df_osm)
                print_source_results("OpenStreetMap", df_osm)
                df_osm.to_csv("data/raw/osm_raw.csv", index=False)
            except Exception as e:
                console.print(f"  [red]✗ OSM failed: {e}[/red]")
            progress.remove_task(task)

        if "historic_england" in run_sources:
            task = progress.add_task("Historic England NHLE...", total=None)
            try:
                from extractors.historic_england_extractor import extract as he_extract
                df_he = he_extract()  # Set True for deeper scan
                source_dfs.append(df_he)
                print_source_results("Historic England", df_he)
                df_he.to_csv("data/raw/historic_england_raw.csv", index=False)
            except Exception as e:
                console.print(f"  [red]✗ Historic England failed: {e}[/red]")
            progress.remove_task(task)

        if "charity_commission" in run_sources:
            task = progress.add_task("Charity Commission...", total=None)
            try:
                from extractors.charity_commission_extractor import extract as cc_extract
                df_cc = cc_extract()
                source_dfs.append(df_cc)
                print_source_results("Charity Commission", df_cc)
                df_cc.to_csv("data/raw/charity_commission_raw.csv", index=False)
            except Exception as e:
                console.print(f"  [red]✗ Charity Commission failed: {e}[/red]")
            progress.remove_task(task)

    if not source_dfs:
        console.print("[red bold]No data extracted from any source. Exiting.[/red bold]")
        raise typer.Exit(1)

    total_raw = sum(len(d) for d in source_dfs)
    console.print(f"\n[bold]Total raw records extracted:[/bold] [cyan]{total_raw:,}[/cyan]")

    # ── TRANSFORMATION ────────────────────────────────────────────────────────
    console.rule("[bold blue]Stage 2: Transform[/bold blue]")

    from transforms.pipeline import (
        combine_sources, clean, geocode_missing,
        enrich_geographic, deduplicate, add_derived_fields, validate,
        fill_region_from_lookup,
    )
    from constants import MASTER_COLUMNS

    console.print("Combining sources...")
    df = combine_sources(*source_dfs)

    console.print("Cleaning...")
    df = clean(df)

    if not skip_geocode:
        console.print("Geocoding missing coordinates (this may take a while)...")
        df = geocode_missing(df, max_geocode=500)
        console.print("Enriching geographic fields...")
        df = enrich_geographic(df)
    else:
        console.print("[dim]Geocoding skipped[/dim]")
        from transforms.pipeline import fill_region_from_lookup
        df = fill_region_from_lookup(df)

    console.print("Deduplicating...")
    df = deduplicate(df)

    console.print("Adding derived fields...")
    df = add_derived_fields(df)

    console.print("Validating...")
    df = validate(df)

    # ── LOAD ──────────────────────────────────────────────────────────────────
    if not dry_run:
        console.rule("[bold blue]Stage 3: Load[/bold blue]")
        from transforms.loader import load
        outputs = load(df)
        console.print("\n[bold]Output files:[/bold]")
        for key, path in outputs.items():
            console.print(f"  [green]{key}:[/green] {path}")
    else:
        console.print("\n[dim]Dry run — no files written[/dim]")

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    print_final_summary(df)
    elapsed = time.time() - start_time
    console.print(f"\n[bold]Total runtime:[/bold] {elapsed:.0f}s ({elapsed/60:.1f} min)\n")


if __name__ == "__main__":
    app()
