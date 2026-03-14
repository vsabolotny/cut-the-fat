import click
from rich.progress import Progress, SpinnerColumn, TextColumn
from .. import db
from ..render.terminal import console, show_upload_result


@click.command()
@click.argument("datei", type=click.Path(exists=True))
@click.option("--kein-ki", is_flag=True, default=False, help="KI-Kategorisierung überspringen")
def cmd(datei: str, kein_ki: bool):
    """Kontoauszug importieren (CSV, Excel oder PDF)."""
    db.ensure_initialized()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Datei wird verarbeitet…", total=None)

        def on_progress(stage: str, count: int):
            if stage == "kategorisierung":
                progress.update(task, description=f"KI kategorisiert {count} Händler…")

        try:
            result = db.ingest_file(datei, progress_cb=on_progress if not kein_ki else None)
        except ValueError as e:
            console.print(f"\n[red]Fehler:[/red] {e}")
            raise SystemExit(1)
        except Exception as e:
            console.print(f"\n[red]Unerwarteter Fehler:[/red] {e}")
            raise SystemExit(1)

    show_upload_result(result)
