"""Writes analytics/YYYY-MM.md reports."""
from datetime import date, datetime
from pathlib import Path

_MONTHS_DE = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _fmt_eur(amount: float) -> str:
    negative = amount < 0
    s = f"{abs(amount):,.2f}"
    s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"-{s} €" if negative else f"{s} €"


def _month_label(month: str) -> str:
    year, mon = int(month[:4]), int(month[5:])
    return f"{_MONTHS_DE[mon]} {year}"


def write_monthly_report(
    month: str,
    summary: dict,
    comparison: dict | None,
    insights_data: dict | None,
) -> Path:
    """Generate analytics/YYYY-MM.md and return its path."""
    analytics_dir = Path(__file__).resolve().parents[2] / "analytics"
    analytics_dir.mkdir(exist_ok=True)
    out = analytics_dir / f"{month}.md"

    lines = []
    lines.append(f"# {_month_label(month)}")
    lines.append("")

    # Summary line
    total = summary["total"]
    if comparison and comparison.get("delta") is not None:
        delta = comparison["delta"]
        pct = comparison.get("delta_pct")
        arrow = "▲" if delta > 0 else "▼"
        pct_str = f" ({abs(pct):.1f}%)" if pct is not None else ""
        prev_label = _month_label(comparison["previous_month"])
        lines.append(
            f"**Gesamt:** {_fmt_eur(total)}  "
            f"{arrow} {_fmt_eur(abs(delta))}{pct_str} vs. {prev_label}"
        )
    else:
        lines.append(f"**Gesamt:** {_fmt_eur(total)}")

    lines.append("")

    # Category table
    cats = summary.get("categories", [])
    if cats:
        lines.append("## Ausgaben nach Kategorie")
        lines.append("")
        lines.append("| Kategorie | Betrag | Anteil |")
        lines.append("|---|---:|---:|")
        for c in cats:
            pct_share = c["total"] / total * 100 if total > 0 else 0
            lines.append(f"| {c['category']} | {_fmt_eur(c['total'])} | {pct_share:.1f}% |")
        lines.append("")

    # Month-over-month category deltas
    if comparison and comparison.get("current_categories"):
        curr = comparison["current_categories"]
        prev = comparison["previous_categories"]
        deltas = []
        for cat in sorted(set(list(curr.keys()) + list(prev.keys()))):
            d = curr.get(cat, 0.0) - prev.get(cat, 0.0)
            if abs(d) > 0.5:
                deltas.append((cat, curr.get(cat, 0.0), prev.get(cat, 0.0), d))
        deltas.sort(key=lambda x: abs(x[3]), reverse=True)

        if deltas:
            prev_label = _month_label(comparison["previous_month"])
            lines.append(f"## Vergleich mit {prev_label}")
            lines.append("")
            lines.append(f"| Kategorie | Aktuell | {prev_label} | Δ |")
            lines.append("|---|---:|---:|---:|")
            for cat, cur, prv, d in deltas[:10]:
                arrow = "▲" if d > 0 else "▼"
                lines.append(f"| {cat} | {_fmt_eur(cur)} | {_fmt_eur(prv)} | {arrow} {_fmt_eur(abs(d))} |")
            lines.append("")

    # Insights
    if insights_data:
        insights = insights_data.get("insights", [])
        if insights:
            lines.append("## KI-Empfehlungen")
            lines.append("")
            for insight in insights:
                text = insight.get("text", "")
                itype = insight.get("type", "info")
                prefix = "> ⚠️" if itype == "warning" else ("> ✅" if itype == "success" else "> ℹ️")
                lines.append(f"{prefix} {text}")
                lines.append(">")
            lines.append("")

    # Footer
    today = datetime.now().strftime("%d.%m.%Y")
    lines.append("---")
    lines.append(f"*Generiert am {today} mit Cut the Fat*")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out
