"""Interactive Q&A agent for categorizing merchants classified as 'Sonstiges'."""
import click
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box
from .. import db
from ..render.terminal import console


def _show_categories(categories: list[str]) -> None:
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Nr.", style="dim", min_width=3)
    table.add_column("Kategorie", style="cyan")

    cols = 3
    cats_per_col = (len(categories) + cols - 1) // cols
    rows = []
    for i in range(cats_per_col):
        row = []
        for c in range(cols):
            idx = i + c * cats_per_col
            if idx < len(categories):
                row.append(f"{idx + 1:>2}. {categories[idx]}")
            else:
                row.append("")
        rows.append("   ".join(row))

    for row in rows:
        console.print(f"   [dim]{row}[/dim]")
    console.print()


@click.command()
@click.option("--limit", default=20, show_default=True, help="Maximale Anzahl Händler pro Sitzung")
def cmd(limit: int):
    """Unkategorisierte Händler interaktiv kategorisieren (Q&A-Agent)."""
    db.ensure_initialized()

    # 1. Fetch uncategorized merchants
    merchants = db.get_uncategorized_merchants()
    if not merchants:
        console.print("\n[green]✓[/green] Alle Händler sind bereits kategorisiert!\n")
        return

    merchants = merchants[:limit]
    categories = db.get_all_categories()

    console.print()
    console.rule("[bold cyan]✂  Kategorien lernen[/bold cyan]")
    console.print(f"\n  {len(merchants)} unkategorisierte Händler gefunden.\n")

    # 2. Get AI batch suggestions
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"KI analysiert {len(merchants)} Händler…", total=None)
        merchant_keys = [m["merchant"] for m in merchants]
        suggestions = db.get_ai_suggestions(merchant_keys, categories)

    # 3. Interactive loop
    console.print("  Befehle: [Enter] = KI-Vorschlag annehmen  |  [Zahl] = Kategorie wählen  |  [t] = eigener Text  |  [q] = beenden\n")
    _show_categories(categories)

    updated = 0
    for m in merchants:
        merchant_key = m["merchant"]
        display = m["display"] or merchant_key
        suggestion = suggestions.get(merchant_key, "Sonstiges")
        count = m["count"]

        console.print(
            f"  [bold white]{display}[/bold white]  "
            f"[dim]({count} Txn)[/dim]  →  [cyan]{suggestion}[/cyan]"
        )

        try:
            answer = click.prompt(
                "   Kategorie [Enter/Zahl/t/q]",
                default="",
                show_default=False,
            ).strip()
        except (click.Abort, KeyboardInterrupt):
            console.print("\n[dim]Abgebrochen.[/dim]")
            break

        if answer.lower() == "q":
            console.print("[dim]Beendet.[/dim]")
            break

        if answer == "":
            chosen = suggestion
        elif answer.lower() == "t":
            chosen = click.prompt("   Eigene Kategorie eingeben").strip()
            if not chosen:
                continue
        elif answer.isdigit():
            idx = int(answer) - 1
            if 0 <= idx < len(categories):
                chosen = categories[idx]
            else:
                console.print("  [red]Ungültige Nummer.[/red]")
                continue
        else:
            console.print("  [red]Unbekannte Eingabe, übersprungen.[/red]")
            continue

        count_updated = db.apply_rule(merchant_key, chosen)
        console.print(f"  [green]✓[/green] [dim]{count_updated} Transaktionen → {chosen}[/dim]\n")
        updated += 1

    console.print(f"\n  [bold]Fertig:[/bold] {updated} Händler kategorisiert.\n")
