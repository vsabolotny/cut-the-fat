import click
from rich.progress import Progress, SpinnerColumn, TextColumn
from .. import db
from ..render.terminal import console, show_insights


@click.command()
@click.option("--neu", is_flag=True, default=False, help="Cache ignorieren und neu generieren")
def cmd(neu: bool):
    """KI-Sparempfehlungen anzeigen."""
    db.ensure_initialized()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Empfehlungen werden geladen…", total=None)
        insights_data = db.get_insights_data(force=neu)

    show_insights(insights_data)
