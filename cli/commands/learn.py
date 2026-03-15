"""Merchant categorisation via Textual TUI."""
import click
from .. import db
from ..render.terminal import console


@click.command()
def cmd():
    """Unkategorisierte Händler interaktiv kategorisieren (TUI)."""
    db.ensure_initialized()
    if not db.get_uncategorized_merchants():
        console.print("\n[green]✓[/green] Alle Händler sind bereits kategorisiert!\n")
        return
    from ..render.tui_learn import LearnApp
    LearnApp().run()
