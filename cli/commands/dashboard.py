from datetime import datetime
import click
from .. import db
from ..render.terminal import console, show_dashboard, show_multi_dashboard


@click.command()
@click.option("--monat", default=None, metavar="JJJJ-MM", help="Einzelner Monat anzeigen")
@click.option("--monate", default=None, type=int, metavar="N", help="Anzahl Monate analysieren (überspringt Abfrage)")
def cmd(monat: str | None, monate: int | None):
    """Ausgabenübersicht — wird nach Analysezeitraum gefragt."""
    db.ensure_initialized()

    # Explicit single month
    if monat:
        summary = db.get_summary(monat)
        comparison = db.get_comparison(monat)
        show_dashboard(summary, comparison)
        return

    # Ask how many months if not provided via flag
    if monate is None:
        try:
            monate = click.prompt(
                "\n  Wie viele Monate analysieren?",
                type=click.IntRange(1, 24),
                default=1,
                show_default=True,
            )
        except (click.Abort, KeyboardInterrupt):
            console.print("\n[dim]Abgebrochen.[/dim]")
            return

    if monate == 1:
        month = db.get_latest_month()
        if not month:
            month = datetime.now().strftime("%Y-%m")
            console.print(f"[dim]Keine Daten vorhanden, zeige aktuellen Monat ({month}).[/dim]")
        summary = db.get_summary(month)
        comparison = db.get_comparison(month)
        show_dashboard(summary, comparison)
    else:
        history = db.get_history(monate)
        show_multi_dashboard(history)
