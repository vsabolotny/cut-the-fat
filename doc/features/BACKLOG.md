# Cut the Fat — Feature Backlog

Dieses Dokument sammelt alle geplanten Features. Sobald ein Feature konkret angegangen wird,
bekommt es ein eigenes PRD (`doc/features/PRD_<name>.md`) nach dem Format in `doc/GUIDELINES.md`.

Status: `💡 Idee` | `📋 PRD offen` | `🔄 In Arbeit` | `✅ Fertig`

---

## Alpha-Releaseblock (jetzt)

### Desktop Auto-Updater aktivieren `🔄 In Arbeit`
Signing-Key generieren, `tauri.conf.json` befüllen, CI-Secret setzen.
Nutzer bekommen Update-Prompt wenn neue Version auf GitHub erscheint.
→ Details in `doc/tauri-desktop.md`

### Sentry + Bug-Reporting `📋 PRD offen`
- Python-Sidecar: `sentry-sdk` mit `FastAPIIntegration`
- Frontend: Sentry Browser SDK
- Sentry → GitHub Issues Integration (automatische Issue-Erstellung bei Crash)
- Bug-Report-Button in Desktop-App ist schon da (`web/handlers/bugreport.py`)

---

## Nächste Iteration

### Multi-Nutzer / Familien-Konten `💡 Idee`
**Problem:** Aktuell Einzelnutzer. Familien haben mehrere Konten, wollen aber
gemeinsame Auswertungen.

**Konzept:**
- Jede Person verwaltet ihr privates Konto lokal — bleibt privat
- Opt-in "Familienkonto" das für alle Mitglieder einsehbar ist
- Peer-to-peer Sync (kein zentraler Server): Kategorien, Händlerregeln und
  Familienkonto-Transaktionen werden zwischen Geräten synchronisiert
- Technologie-Kandidaten: lokales Netzwerk (mDNS), encrypted file sync
  (Syncthing-Protokoll), oder geteilter verschlüsselter S3-Bucket als Mittler

**Offene Fragen:**
- Konfliktauflösung bei gleichzeitiger Bearbeitung von Händlerregeln
- Granularität der Freigabe: ganzes Konto oder nur Kategoriesummen?
- Onboarding: wie verbinden sich zwei Geräte zum ersten Mal?

---

### Kredite, Sparen & Rücklagen `💡 Idee`
**Problem:** Dashboard zeigt nur Monatsausgaben. Längere Finanzplanung fehlt.

**Konzept:**
- Laufende Kredite mit Restlaufzeit und Monatsrate erfassen
- Sparrücklage-Ziele definieren (z.B. "Notfallreserve: 3 Monatsgehälter")
- Übersicht: "Gebundenes Kapital" (Kredite) vs. "Freies Kapital" (Rücklagen)
- Zeitachsen-Chart über 12–36 Monate

---

### Steuerliche Kategorien `💡 Idee`
**Problem:** Manche Ausgaben sind steuerlich absetzbar, aber man muss sie
manuell heraussuchen.

**Konzept:**
- Zusätzliches Flag `steuerlich_absetzbar` auf Kategorien/Transaktionen
- Vordefinierte steuerliche Gruppen: Arbeitsmittel, Gesundheit, Porto/Versand,
  Kinderbetreuung, Fortbildung, Spenden
- Jahresauswertung: "Absetzbare Ausgaben 2025" als PDF-Export
- Nicht: Steuerberechnung — nur Zusammenfassung für den Steuerberater

---

### Jährliche Buchungen einrechnen `💡 Idee`
**Problem:** Versicherungen, Mitgliedsbeiträge, Jahresgebühren verzerren den
Monatsvergleich und fehlen in der "Was kann ich mir leisten?"-Auswertung.

**Konzept:**
- Manuelle Erfassung von jährlich/quartalsweise anfallenden Buchungen
  (Betrag + Fälligkeitsmonat)
- Dashboard zeigt monatlich anteiligen Betrag ("kalkulatorische Rücklage")
- Warnung wenn Fälligkeitsmonat näher rückt und Rücklage nicht ausreicht
- Import: aus bereits kategorisierten Transaktionen der letzten 12 Monate
  automatisch Kandidaten vorschlagen

---

### Mehrsprachigkeit `💡 Idee`
**Problem:** App ist auf Deutsch. Nicht-Muttersprachler können Kontotransaktionen
(meist Deutsch/Englisch) schwer lesen und zuordnen.

**Konzept:**
- UI-Sprache: DE/EN als erster Schritt, weitere per Community-Beitrag
- Transaktions-Translation: Händlernamen und Buchungstext werden optional in
  die Sprache des Nutzers übersetzt (via Claude, gecacht in DB)
- Kategorienamen bleiben intern auf Deutsch (kanonische Liste), werden in der
  UI in der gewählten Sprache angezeigt
- Privacy-Aspekt: Translation-Calls an Anthropic müssen als Datentransfer
  sichtbar sein (gilt für alle AI-Calls, siehe EU AI Act unten)

---

### EU AI Act — Transparenz & Datenschutz `💡 Idee`
**Problem:** Wenn Nutzerdaten die App verlassen, muss das erklärbar sein.
Der EU AI Act verlangt Transparenz bei AI-unterstützten Entscheidungen.

**Konzept (Drill-Down-Modell):**
- Level 0 (immer sichtbar): ⚠️-Icon bei jedem Feature das AI nutzt
- Level 1 (ein Klick): "Was wird gesendet?" — Zusammenfassung des Payloads
- Level 2 (zwei Klicks): Rohes JSON/Prompt das an Anthropic geht
- Level 3 (optional): Modell, max_tokens, Systemprompt

**Datenanonymisierung:**
- Kategorisierung nutzt bereits nur normalisierte Händlernamen (gut)
- Insights: Beträge auf ganze Euro runden vor dem API-Call
- Optional: Händlernamen durch generische Labels ersetzen wenn Nutzer das will
  ("Supermarkt A" statt "REWE Musterstr.") — reduziert Re-Identifizierbarkeit

---

### Diagnose & QA-Modus `💡 Idee`
**Problem:** Da hauptsächlich AI den Code schreibt, muss es einfach sein
nachzuvollziehen was passiert, was gecacht ist und was in der DB landet.

**Konzept:**
- `/debug`-Seite in der Web-UI (nur dev-mode): DB-Row-Counts, Cache-Status,
  letzte Uploads, letzter AI-Call + Response
- CLI-Kommando `./ctf debug` mit strukturiertem Output
- "Was liegt im Cache?" — zeigt alle Insights-Cache-Einträge mit Alter und Key
- "Was wurde übertragen?" — Log aller externen API-Calls mit Timestamp und
  Payload-Größe (lokal, nicht an Sentry)
- Export: `./ctf export-diagnostics` → ZIP mit anonymisiertem DB-Dump +
  Log-Ausschnitt für Bug-Reports

---

## Zurückgestellt

### Mobile App `💡 Idee`
Zunächst als PWA (Progressive Web App) — responsive Web-App auf Homescreen.
Tauri Mobile (iOS/Android) ist technisch möglich ab Tauri 2, aber das Tooling
ist noch unreif. Evaluierung wenn Desktop stabil läuft.

---

## Fertig

- CLI (upload, dashboard, insights, learn, report) ✅
- Web-UI (Chat + Dashboard + Insights + Transactions) ✅
- Tauri Desktop-App mit Python-Sidecar ✅
- Bug-Report-Button → GitHub Issues ✅
- GitHub Actions CI/CD Release-Pipeline ✅
- Anthropic-Transparenz in der Web-UI ✅
