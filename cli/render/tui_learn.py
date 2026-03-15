"""Textual TUI for interactive merchant categorisation."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    LoadingIndicator,
    Select,
    Static,
)
from textual.widgets._select import NoSelection
from textual.worker import get_current_worker

from .. import db


# ---------------------------------------------------------------------------
# Category selection modal
# ---------------------------------------------------------------------------

class CategoryModal(ModalScreen[str | None]):
    """Overlay for picking a category for one merchant."""

    DEFAULT_CSS = """
    CategoryModal {
        align: center middle;
    }
    CategoryModal > #dialog {
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        width: 60;
        height: auto;
    }
    CategoryModal > #dialog > Label {
        margin-bottom: 1;
    }
    CategoryModal > #dialog > Select {
        margin-bottom: 1;
    }
    CategoryModal > #dialog > Horizontal {
        height: auto;
        align-horizontal: right;
    }
    CategoryModal > #dialog > Horizontal > Button {
        margin-left: 1;
    }
    """

    def __init__(self, merchant_display: str, current: str | None, categories: list[str]) -> None:
        super().__init__()
        self._merchant_display = merchant_display
        self._current = current
        self._categories = categories

    def compose(self) -> ComposeResult:
        options = [(cat, cat) for cat in self._categories]
        with Vertical(id="dialog"):
            yield Label(f"Händler: [bold]{self._merchant_display}[/bold]")
            if self._current:
                yield Select(options, value=self._current, id="cat-select")
            else:
                yield Select(options, id="cat-select")
            with Horizontal():
                yield Button("Abbrechen", variant="default", id="cancel")
                yield Button("OK", variant="primary", id="ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            sel = self.query_one("#cat-select", Select)
            if isinstance(sel.value, NoSelection):
                self.dismiss(None)
            else:
                self.dismiss(str(sel.value))


# ---------------------------------------------------------------------------
# Main TUI app
# ---------------------------------------------------------------------------

class LearnApp(App):
    """TUI for categorising uncategorised merchants."""

    TITLE = "✂  Kategorien lernen"
    BINDINGS = [
        Binding("a", "accept_all", "Alle annehmen"),
        Binding("s", "save", "Speichern"),
        Binding("q", "quit_app", "Beenden"),
        Binding("escape", "quit_app", "Beenden"),
        Binding("enter,space", "open_modal", "Kategorie wählen", show=True),
    ]
    DEFAULT_CSS = """
    #status-bar {
        height: 1;
        padding: 0 1;
        background: $boost;
        color: $text-muted;
    }
    #loading {
        height: 3;
    }
    #merchant-table {
        height: 1fr;
    }
    #button-bar {
        height: 3;
        align-horizontal: right;
        padding: 0 1;
    }
    #button-bar > Button {
        margin-left: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._merchants: list[dict] = []
        self._suggestions: dict[str, str] = {}
        self._categories: list[str] = []
        self._choices: dict[str, str | None] = {}

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Lade Daten…", id="status-bar")
        yield LoadingIndicator(id="loading")
        table = DataTable(id="merchant-table", cursor_type="row", zebra_stripes=True)
        table.display = False
        yield table
        bar = Horizontal(id="button-bar")
        bar.display = False
        with bar:
            yield Button("Alle annehmen  [a]", variant="primary", id="btn-accept")
            yield Button("Speichern  [s]", variant="success", id="btn-save")
        yield Footer()

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        self.run_worker(self._fetch_data, thread=True)

    def _fetch_data(self) -> None:
        worker = get_current_worker()
        merchants = db.get_uncategorized_merchants()
        if worker.is_cancelled:
            return
        categories = db.get_all_categories()
        if worker.is_cancelled:
            return
        keys = [m["merchant"] for m in merchants]
        suggestions = db.get_ai_suggestions(keys, categories) if keys else {}
        if not worker.is_cancelled:
            self.call_from_thread(self._on_data_ready, merchants, categories, suggestions)

    def _on_data_ready(
        self,
        merchants: list[dict],
        categories: list[str],
        suggestions: dict[str, str],
    ) -> None:
        self._merchants = merchants
        self._categories = categories
        self._suggestions = suggestions
        self._choices = {m["merchant"]: None for m in merchants}

        # Hide spinner, show table + buttons
        self.query_one("#loading").display = False
        table = self.query_one("#merchant-table", DataTable)
        table.display = True
        self.query_one("#button-bar").display = True

        # Build table
        table.add_columns("#", "Händler", "Txn", "KI-Vorschlag", "Gewählt")
        for i, m in enumerate(merchants, 1):
            key = m["merchant"]
            suggestion = suggestions.get(key, "Sonstiges")
            table.add_row(
                str(i),
                m["display"] or key,
                str(m["count"]),
                suggestion,
                "",
                key=key,
            )

        self._update_status()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_status(self) -> None:
        done = sum(1 for v in self._choices.values() if v is not None)
        total = len(self._choices)
        self.query_one("#status-bar", Static).update(
            f"{done} / {total} kategorisiert"
        )

    def _refresh_table(self) -> None:
        table = self.query_one("#merchant-table", DataTable)
        for m in self._merchants:
            key = m["merchant"]
            chosen = self._choices.get(key)
            table.update_cell(key, "Gewählt", chosen or "")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_modal(self) -> None:
        table = self.query_one("#merchant-table", DataTable)
        if table.cursor_row < 0 or not self._merchants:
            return
        row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
        merchant_key = str(row_key.value)
        m = next((x for x in self._merchants if x["merchant"] == merchant_key), None)
        if m is None:
            return
        display = m["display"] or merchant_key
        current = self._choices.get(merchant_key) or self._suggestions.get(merchant_key)
        self.push_screen(
            CategoryModal(display, current, self._categories),
            lambda result: self._on_modal_result(merchant_key, result),
        )

    def _on_modal_result(self, merchant_key: str, result: str | None) -> None:
        if result is None:
            return
        self._choices[merchant_key] = result
        table = self.query_one("#merchant-table", DataTable)
        table.update_cell(merchant_key, "Gewählt", result)
        self._update_status()

    def action_accept_all(self) -> None:
        for m in self._merchants:
            key = m["merchant"]
            if self._choices.get(key) is None:
                self._choices[key] = self._suggestions.get(key, "Sonstiges")
        self._refresh_table()
        self._update_status()

    def action_save(self) -> None:
        self.run_worker(self._do_save, thread=True)

    def _do_save(self) -> None:
        count = 0
        for key, chosen in self._choices.items():
            if chosen:
                db.apply_rule(key, chosen)
                count += 1
        self.call_from_thread(self._on_save_done, count)

    def _on_save_done(self, count: int) -> None:
        self.notify(f"{count} Händler gespeichert.", title="Gespeichert", timeout=3)
        self.set_timer(1.5, self.exit)

    def action_quit_app(self) -> None:
        self.exit()

    # ------------------------------------------------------------------
    # Button clicks
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-accept":
            self.action_accept_all()
        elif event.button.id == "btn-save":
            self.action_save()
