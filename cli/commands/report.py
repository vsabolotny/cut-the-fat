from datetime import datetime
import click
from rich.progress import Progress, SpinnerColumn, TextColumn
from .. import db
from ..render.terminal import console
from ..render.md_writer import write_monthly_report


@click.command()
@click.option("--monat", default=None, metavar="JJJJ-MM", help="Monat (Standard: letzter Monat mit Daten)")
@click.option("--alle", is_flag=True, default=False, help="Berichte für alle verfügbaren Monate generieren")
def cmd(monat: str | None, alle: bool):
    """Monatsbericht als Markdown-Datei generieren (analytics/JJJJ-MM.md)."""
    db.ensure_initialized()

    if alle:
        months = _get_all_months()
        if not months:
            console.print("[dim]Keine Daten vorhanden.[/dim]")
            return
        console.print(f"\n  {len(months)} Monate werden generiert…\n")
        for m in months:
            _generate_report(m)
        console.print()
        return

    if not monat:
        monat = db.get_latest_month()
        if not monat:
            monat = datetime.now().strftime("%Y-%m")

    _generate_report(monat)


def _get_all_months() -> list[str]:
    import asyncio
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    async def _fetch():
        async with AsyncSessionLocal() as db_:
            r = await db_.execute(
                text("SELECT DISTINCT strftime('%Y-%m', date) as m FROM transactions WHERE type='debit' ORDER BY m")
            )
            return [row[0] for row in r.all()]

    return asyncio.run(_fetch())


def _generate_report(monat: str) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"Generiere Bericht für {monat}…", total=None)
        summary = db.get_summary(monat)
        comparison = db.get_comparison(monat)
        insights_data = db.get_insights_data()

    path = write_monthly_report(monat, summary, comparison, insights_data)
    total = summary["total"]
    console.print(
        f"  [green]✓[/green] [bold]{path.name}[/bold]  "
        f"[dim]{len(summary['categories'])} Kategorien, {_fmt_eur(total)} gesamt[/dim]"
    )


def _fmt_eur(amount: float) -> str:
    s = f"{abs(amount):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{s} €"
