## PRD — Cut the Fat (UI/App, Privacy-first)

### Kontext (aus eurem Chat)
- **Problem**: Tool ist aktuell CLI-only; wiederholte Reports/Insights/Uploads sind im Terminal unbequem.
- **Zielbild**: “Ideal wäre eine App” (lokal nutzbar, einfacher Zugriff, wiederholbare Reports).
- **Kritischer Punkt**: Kontodaten sollen **nicht** an Anthropic/extern gehen. Ist-Zustand: Upload-Kategorisierung + Insights senden Daten an Anthropic, wenn `ANTHROPIC_API_KEY` gesetzt ist.
- **Stage**: Erst “für uns”, später teilbar + Feedback evaluieren.

### Produktziele
- **UI statt Terminal**: Alltags-Workflows (Upload → Kategorisierung → Dashboard/Report/Insights) per GUI ausführbar.
- **Transparente Datenflüsse**: UI zeigt klar, wenn Daten an Anthropic/extern gesendet werden.
- **Reproduzierbarkeit**: Reports/Insights mit 1 Klick neu generieren; klare “Cache/Neu”-Optionen.
- **Zuverlässigkeit**: Keine Server-Abhängigkeit; lokale SQLite bleibt Source of Truth.

### Nicht-Ziele (vorerst)
- **Bank-Connect/PSD2**: Kein Live-Banking-Connector im MVP.
- **Multi-User / Cloud Sync**: Kein Account-System, kein Hosting.
- **Komplexe Budgetplanung**: Keine langfristigen Forecasts/Planbudgets im MVP.
- **Backend-Refactor im ersten Schritt**: Keine Änderungen an bestehender Kategorisierung/Insights-Logik (inkl. Anthropic-Calls bleiben unverändert).

### Zielgruppe
- **Primary**: Vlad & Paul (Einzelnutzer, lokal, deutsch).
- **Secondary (später)**: Freunde/Bekannte, die lokal bleiben wollen.

### Ist-Zustand (Repo-Fakten)
- **CLI Entry**: `./ctf` → Click-Kommandos: `upload/dashboard/insights/learn/report`.
- **Backend**: Async Services + SQLite (`backend/cut_the_fat.db`), keine HTTP-Schicht.
- **LLM-Nutzung**:
  - `backend/app/services/categorizer.py`: `categorize_merchants()` nutzt Anthropic, sonst Fallback `Sonstiges`.
  - `backend/app/services/insights.py`: `get_insights()` nutzt Anthropic, sonst rule-based Fallback.
- **Reports**: Markdown nach `analytics/YYYY-MM.md`.

### MVP Scope (UI v0)
#### Kern-Features
- **Upload**: Datei auswählen (CSV/Excel/PDF) → Import starten → Fortschritt/Ergebnis anzeigen.
- **Dashboard**: Monat auswählen → Kategorie-Summen + Top-Merchants (wie CLI).
- **Insights**: Anzeigen + Button “Neu generieren” (entspricht `--neu`).
- **Learn / Regeln**: Unkategorisierte Händler anzeigen → Kategorie setzen → Regel speichern.
- **Report**: Report für Monat generieren (Markdown), anzeigen + “Datei öffnen”.

#### Privacy/Offline Anforderungen (MVP)
- **Keine Funktionsänderung**: Anthropic-Aufrufe bleiben im bestehenden Code aktiv, so wie heute (abhängig von `ANTHROPIC_API_KEY` und den bestehenden CLI-Flows).
- **Prominente Warnung in der UI**: Wenn ein Flow Daten an Anthropic sendet, muss die UI das sichtbar markieren (z.B. Label “sendet Daten an Anthropic” + Ausrufezeichen).
- **Detailanzeige per Ausrufezeichen**: In einer Detailansicht sieht man **genau den Payload**, der an Anthropic übertragen wird:
  - **Kategorisierung**: Liste der Händler (wie im Prompt formatiert).
  - **Insights**: Das aggregierte Ausgaben-JSON (formatiert, pretty-printed).
  - Optional zusätzlich: Modellname + max_tokens + Systemprompt (rein zur Transparenz).

### Erweiterungen (nach MVP)
- **Lokales Kategorisierungsmodell**: Kleines lokales Modell (oder klassische Heuristiken + Rules), später optional lokales LLM via Ollama/LM Studio.
- **Lokale Insights**: Regel-/Statistik-basiert ausbauen (keine LLM nötig).
- **Import-Automation**: “Watch folder” für Kontoauszüge.
- **Onboarding**: Guided Setup (DB/Statements-Ordner, Kategorien, Datenschutz).

### UX-Anforderungen
- **Schnellstart**: App öffnen → “Letzter Monat” automatisch anzeigen, wenn Daten existieren.
- **Transparenz**: Immer sichtbar, ob ein Flow Daten an Anthropic sendet (inkl. Detailansicht mit Payload).
- **Fehlertoleranz**: Parser-Fehler verständlich; Import-Rollback/Teilimport klar kommunizieren.

### Technische Anforderungen (MVP)
- **Plattform**: macOS zuerst; später Windows/Linux optional.
- **Lokal**: SQLite bleibt; keine externen Server.
- **Prozessmodell**:
  - UI ruft die bestehenden Python-Services direkt auf (embedded) oder via lokalem Prozess (subprocess).
  - Keine neue HTTP-API im MVP (passt zur Repo-Entscheidung “kein HTTP layer”).

### Engineering Notes (was wir beim ersten UI-Run fixen mussten)
- **Webapp-Start**: Für das lokale Ansehen braucht es eine Python-venv + installierte Dependencies (z.B. `sqlalchemy`), sonst startet `web/app.py` nicht.
- **Anthropic-Indikation**:
  - **Ohne** `.env` / `ANTHROPIC_API_KEY`: UI muss klar zeigen, dass **nichts** gesendet wird.
  - **Mit** Key: UI muss pro Feature (“Insights”, “Learn”) prominent markieren, dass Daten gesendet werden, und per `!` den **konkreten Payload** anzeigen (pretty-printed JSON/Prompt).
- **Report-Generierung (Web)**:
  - Bug: `web/handlers/report.py` importierte eine nicht existierende Funktion `generate_report` aus `cli.render.md_writer`.
  - Fix: Web nutzt `write_monthly_report(...)` direkt und bezieht Daten via `app.queries`.
  - Bug: freie Texte wie „Bericht erstellen“ konnten als “month” falsch geparst werden (z.B. `erst…`) → Crash; daher akzeptiert der Web-Report nur `YYYY-MM` und fällt sonst auf “letzter Monat mit Daten” zurück.

### Akzeptanzkriterien (MVP)
- **Upload**: Eine Beispieldatei importieren, ohne Terminal zu öffnen.
- **Dashboard/Insights/Report**: Mind. ein Monat kann vollständig angezeigt/generiert werden.
- **Transparenz (Anthropic)**: Wenn Anthropic genutzt wird, ist das in der UI klar markiert, und der konkrete Payload ist per Ausrufezeichen als formatiertes JSON/Prompt einsehbar.
- **Learn/Rules**: Eine Händlerregel setzen und bei neuem Import greift sie.

