"""Rich terminal rendering helpers."""
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


def fmt_eur(amount: float) -> str:
    """Format a number as German currency: 1.234,56 €"""
    negative = amount < 0
    s = f"{abs(amount):,.2f}"
    s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"-{s} €" if negative else f"{s} €"


def _bar(value: float, max_value: float, width: int = 20) -> str:
    if max_value <= 0:
        return ""
    filled = int(round(value / max_value * width))
    return "█" * filled + "░" * (width - filled)


_NATALIE_MARKER = "Natalie"


def _split_natalie(cats: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split categories into (main, natalie) lists."""
    main = [c for c in cats if _NATALIE_MARKER not in c["category"]]
    natalie = [c for c in cats if _NATALIE_MARKER in c["category"]]
    return main, natalie


def _expenses_table(cats: list[dict], total: float) -> Table:
    max_val = cats[0]["total"] if cats else 1
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    table.add_column("Kategorie", style="white", min_width=20)
    table.add_column("Betrag", justify="right", style="cyan", min_width=12)
    table.add_column("Anteil", justify="right", min_width=6)
    table.add_column("", min_width=22)
    for c in cats:
        pct_share = c["total"] / total * 100 if total > 0 else 0
        bar = _bar(c["total"], max_val, 20)
        table.add_row(
            c["category"],
            fmt_eur(c["total"]),
            f"{pct_share:.1f}%",
            f"[cyan]{bar}[/cyan]",
        )
    return table


def show_dashboard(summary: dict, comparison: dict | None) -> None:
    month = summary["month"]
    total = summary["total"]
    cats = summary["categories"]

    main_cats, natalie_cats = _split_natalie(cats)
    main_total = sum(c["total"] for c in main_cats)
    natalie_total = sum(c["total"] for c in natalie_cats)

    # Header
    console.print()
    console.rule(f"[bold cyan]✂  Cut the Fat — {month}[/bold cyan]")
    console.print()

    # Delta line
    if comparison and comparison.get("delta") is not None:
        delta = comparison["delta"]
        pct = comparison.get("delta_pct")
        arrow = "▲" if delta > 0 else "▼"
        color = "red" if delta > 0 else "green"
        pct_str = f" ({abs(pct):.1f}%)" if pct is not None else ""
        console.print(
            f"  [bold]Gesamt:[/bold] [white]{fmt_eur(total)}[/white]  "
            f"[{color}]{arrow} {fmt_eur(abs(delta))} vs. Vormonat{pct_str}[/{color}]"
        )
    else:
        console.print(f"  [bold]Gesamt:[/bold] [white]{fmt_eur(total)}[/white]")

    console.print()

    if not cats:
        console.print("  [dim]Keine Transaktionen für diesen Monat.[/dim]")
        return

    income_all = summary.get("income", [])
    main_income = [i for i in income_all if _NATALIE_MARKER not in i.get("category", "")]
    natalie_income = [i for i in income_all if _NATALIE_MARKER in i.get("category", "")]
    main_income_total = sum(i["total"] for i in main_income)
    natalie_income_total = sum(i["total"] for i in natalie_income)

    # Main expenses
    console.rule("[bold]Ausgaben[/bold]", style="cyan")
    console.print()
    console.print(_expenses_table(main_cats, main_total))
    console.print(f"  [bold]Gesamt:[/bold] [cyan]{fmt_eur(main_total)}[/cyan]")

    # Natalie section
    if natalie_cats or natalie_income:
        nat_saldo = natalie_income_total - natalie_total
        nat_saldo_color = "green" if nat_saldo >= 0 else "red"
        console.rule("[bold]Natalie[/bold]", style="magenta")
        console.print()
        if natalie_cats:
            ntable = _expenses_table(natalie_cats, natalie_total)
            for col in ntable.columns:
                if col.style == "cyan":
                    col.style = "magenta"
            console.print(ntable)
        if natalie_income:
            nitable = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
            nitable.add_column("Eingang", style="white", min_width=30)
            nitable.add_column("Betrag", justify="right", style="green", min_width=12)
            for i in natalie_income:
                nitable.add_row(i["merchant"], fmt_eur(i["total"]))
            console.print(nitable)
        console.print(
            f"  [bold]Ausgaben:[/bold] [magenta]{fmt_eur(natalie_total)}[/magenta]  "
            f"│  [bold]Einnahmen:[/bold] [green]{fmt_eur(natalie_income_total)}[/green]  "
            f"│  Saldo: [{nat_saldo_color}]{fmt_eur(nat_saldo)}[/{nat_saldo_color}]"
        )

    # Main income
    if main_income:
        main_saldo = main_income_total - main_total
        main_saldo_color = "green" if main_saldo >= 0 else "red"
        console.rule("[bold]Einnahmen[/bold]", style="green")
        console.print()
        itable = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        itable.add_column("Eingang", style="white", min_width=30)
        itable.add_column("Betrag", justify="right", style="green", min_width=12)
        for i in main_income:
            itable.add_row(i["merchant"], fmt_eur(i["total"]))
        console.print(itable)
        console.print(
            f"  [bold]Gesamt:[/bold] [green]{fmt_eur(main_income_total)}[/green]  "
            f"│  Saldo: [{main_saldo_color}]{fmt_eur(main_saldo)}[/{main_saldo_color}]"
        )


_MONTHS_DE = [
    "", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
]


def _month_short(month: str) -> str:
    mon = int(month[5:])
    year = month[2:4]
    return f"{_MONTHS_DE[mon]} '{year}"


def show_multi_dashboard(history: dict) -> None:
    months = history["months"]
    categories = history["categories"]
    data = history["data"]
    monthly_totals = history["monthly_totals"]

    if not months:
        console.print("  [dim]Keine Daten im gewählten Zeitraum.[/dim]")
        return

    label = f"{_month_short(months[0])} – {_month_short(months[-1])}" if len(months) > 1 else _month_short(months[0])
    console.print()
    console.rule(f"[bold cyan]✂  Cut the Fat — {label}  ({len(months)} Monate)[/bold cyan]")
    console.print()

    # --- Monthly totals row ---
    overall_total = sum(t["total"] for t in monthly_totals)
    console.print(f"  [bold]Gesamt ({len(months)} Monate):[/bold] [white]{fmt_eur(overall_total)}[/white]  "
                  f"[dim]∅ {fmt_eur(overall_total / len(months))}/Monat[/dim]")
    console.print()

    # Monthly totals table
    mtable = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    mtable.add_column("Monat", style="white", min_width=10)
    mtable.add_column("Gesamt", justify="right", style="cyan", min_width=12)
    mtable.add_column("vs. Vormonat", justify="right", min_width=14)
    mtable.add_column("", min_width=16)

    max_monthly = max((t["total"] for t in monthly_totals), default=1)
    for i, mt in enumerate(monthly_totals):
        if i > 0:
            delta = mt["total"] - monthly_totals[i - 1]["total"]
            prev = monthly_totals[i - 1]["total"]
            arrow = "▲" if delta > 0 else "▼"
            color = "red" if delta > 0 else "green"
            pct = abs(delta / prev * 100) if prev else 0
            delta_str = f"[{color}]{arrow} {fmt_eur(abs(delta))} ({pct:.0f}%)[/{color}]"
        else:
            delta_str = "[dim]—[/dim]"
        bar = _bar(mt["total"], max_monthly, 14)
        mtable.add_row(_month_short(mt["month"]), fmt_eur(mt["total"]), delta_str, f"[cyan]{bar}[/cyan]")

    console.print(mtable)

    # --- Aggregated category breakdown ---
    cat_totals = [
        {"category": cat, "total": sum(data[cat])}
        for cat in categories
    ]
    cat_totals.sort(key=lambda x: x["total"], reverse=True)
    max_cat = cat_totals[0]["total"] if cat_totals else 1

    console.print("  [bold dim]Kategorien (gesamt)[/bold dim]")
    console.print()
    ctable = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    ctable.add_column("Kategorie", style="white", min_width=20)
    ctable.add_column("Gesamt", justify="right", style="cyan", min_width=12)
    ctable.add_column("∅/Monat", justify="right", min_width=12)
    ctable.add_column("Anteil", justify="right", min_width=6)
    ctable.add_column("", min_width=20)

    for c in cat_totals:
        pct_share = c["total"] / overall_total * 100 if overall_total > 0 else 0
        avg = c["total"] / len(months)
        bar = _bar(c["total"], max_cat, 18)
        ctable.add_row(
            c["category"],
            fmt_eur(c["total"]),
            fmt_eur(avg),
            f"{pct_share:.1f}%",
            f"[cyan]{bar}[/cyan]",
        )

    console.print(ctable)

    # --- Per-category trend (only if > 1 month) ---
    if len(months) > 1 and len(categories) > 0:
        console.print("  [bold dim]Trend pro Kategorie[/bold dim]")
        console.print()
        ttable = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        ttable.add_column("Kategorie", style="white", min_width=20)
        for m in months:
            ttable.add_column(_month_short(m), justify="right", min_width=10)

        # show top 8 categories by total only
        top_cats = [c["category"] for c in cat_totals[:8]]
        for cat in top_cats:
            row_vals = []
            vals = data[cat]
            max_val = max(vals) if vals else 1
            for v in vals:
                if v == 0:
                    row_vals.append("[dim]—[/dim]")
                elif v == max_val:
                    row_vals.append(f"[bold cyan]{fmt_eur(v)}[/bold cyan]")
                else:
                    row_vals.append(fmt_eur(v))
            ttable.add_row(cat, *row_vals)

        console.print(ttable)


def show_insights(insights_data: dict) -> None:
    insights = insights_data.get("insights", [])
    cached = insights_data.get("cached", False)
    generated_at = insights_data.get("generated_at")

    console.print()
    console.rule("[bold cyan]✂  Empfehlungen[/bold cyan]")
    console.print()

    if not insights:
        console.print("  [dim]Keine Empfehlungen verfügbar.[/dim]")
        return

    type_styles = {
        "warning": ("red", "⚠ "),
        "info":    ("blue", "ℹ "),
        "success": ("green", "✓ "),
    }

    for insight in insights:
        itype = insight.get("type", "info")
        color, icon = type_styles.get(itype, ("white", "• "))
        text = insight.get("text", "")
        console.print(Panel(
            f"[{color}]{icon}[/{color}]{text}",
            border_style=color,
            padding=(0, 1),
        ))

    if cached and generated_at:
        if isinstance(generated_at, str):
            ts = generated_at[:16]
        elif isinstance(generated_at, datetime):
            ts = generated_at.strftime("%Y-%m-%d %H:%M")
        else:
            ts = str(generated_at)
        console.print(f"\n  [dim]Aus Cache (generiert: {ts})[/dim]")
    console.print()


def show_learn_table(merchants: list[dict], suggestions: dict[str, str]) -> None:
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    table.add_column("#", style="dim", min_width=3)
    table.add_column("Händler", style="white", min_width=30)
    table.add_column("Txn", justify="right", min_width=4)
    table.add_column("KI-Vorschlag", style="cyan", min_width=20)

    for i, m in enumerate(merchants, 1):
        suggestion = suggestions.get(m["merchant"], "Sonstiges")
        table.add_row(str(i), m["display"] or m["merchant"], str(m["count"]), suggestion)

    console.print(table)


def show_upload_result(result: dict) -> None:
    console.print()
    console.print(Panel(
        f"[green]✓[/green] [bold]{result['filename']}[/bold]\n"
        f"  Importiert: [cyan]{result['imported']}[/cyan] Transaktionen\n"
        f"  Übersprungen (Duplikate): [dim]{result['skipped']}[/dim]\n"
        f"  Geparst gesamt: [dim]{result['parsed']}[/dim]",
        title="Upload abgeschlossen",
        border_style="green",
    ))
    console.print()
