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

### csv_parser-Tests auf `main` reparieren `✅ Fertig`
Erledigt in PR #6 (CAT-25). Root Cause: **die Tests waren veraltet, nicht der Parser.**
Commit `06980bf` (2026-05-03) hat die Vorzeichen-Konvention bewusst auf
`negativ = Ausgabe` gedreht, die Fixtures aber nie nachgezogen. Gegen einen echten
Postbank-Export verifiziert (`-8,xx` Kartenzahlung, `+500` Bargeldeinzahlung) und
die Fixtures umgestellt. Dieselbe gedrehte Konvention steckte noch in beiden
generischen Pfaden von `pdf_parser.py` und wurde mitkorrigiert.

Verbleibend rot in einem frischen Worktree: die 10 `test_history_integrity`-Tests —
siehe eigener Eintrag unten.

---

## Nächste Iteration

### Redesign-Variante aus CAT-26 umsetzen `💡 Idee`
**Problem:** CAT-26 hat 3 Prototyp-Varianten geliefert
(`doc/design/CAT-26-frontend-redesign/prototype.html`), die Web-UI selbst ist unverändert.

- **Priorität:** P2 — kein Nutzer wartet akut, aber die Analyse (DECISIONS.md §1)
  benennt konkrete UX-Schulden der heutigen Chat-first-UI; wird P1, sobald Alpha-Nutzer
  das Tracking regelmäßig verwenden.
- **Auslöser:** Deliverable-Sichtung steht aus — Variante wählen (Empfehlung: 1 „Fluss"),
  dann Umsetzungs-Ticket schneiden.
- **Scope:** Gewählte Variante in `web/static/` umsetzen; aus Variante 2 den laufenden
  Saldo als Detail übernehmen. Out: CLI, Desktop-Shell.
- **Größe:** M · **Quelle:** CAT-26 / PR #5 · 2026-08-27

### chart.js + marked lokal bündeln statt CDN `💡 Idee`
**Problem:** `web/static/index.html:8–13` lädt chart.js und marked von jsdelivr.
Die Desktop-App (Tauri, lokale SQLite, offline-first-Anspruch) verliert damit
Chat-Charts und Markdown-Rendering, sobald kein Internet da ist.

- **Priorität:** P2 — offline ist ein Produktversprechen der Desktop-App; P3, falls
  entschieden wird, dass Desktop faktisch immer online läuft (KI-Calls brauchen ohnehin Netz).
- **Auslöser:** CAT-26-Analyse; der Prototyp zeigt, dass die Flussleiste ohne chart.js geht.
- **Scope:** Beide Libs vendoren (`web/static/vendor/`), CSP-Hashes in Tauri-Config anpassen.
- **Größe:** S · **Quelle:** CAT-26 / PR #5 · 2026-08-27

---

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

## Aus dem Import Mai–Juli 2026 (CAT-25)

### Konto-/Quellen-Dimension in `transactions` `💡 Idee`
**Problem:** `transactions` kennt nur `upload_id`, keine Konto- oder Quellen-Zuordnung.
PayPal- und Kreditkartenzahlungen erscheinen zweimal in der DB: einmal als
Sammellastschrift auf dem Girokonto, einmal als Einzelposten aus dem Detailauszug.
`./ctf dashboard` summiert über alle Uploads und zählt sie damit doppelt.

- **Priorität:** P1 — die Zahlen, die das Tool anzeigt, sind bei gemischten Quellen
  schlicht falsch, und man sieht es ihnen nicht an. Wäre P2, wenn nur eine Quelle
  importiert würde; sobald Kreditkarte oder PayPal dazukommt, ist es P1.
- **Auslöser:** Mai–Juli 2026: Dashboard zeigt 33.340 € Ausgaben, giro-basiert sind es
  29.511 €. Differenz ≈ 3.830 € doppelt gezählte PayPal-/Kartenumsätze.
- **Scope:** Spalte `account` (oder FK auf eine `accounts`-Tabelle) auf `transactions`,
  gesetzt beim Import aus dem erkannten Format. Dashboard/Insights filtern auf das
  Girokonto als Ground Truth, Detailquellen nur zur Aufschlüsselung. Nicht im Scope:
  Multi-Account-UI, Kontoverwaltung.
- **Größe:** M · **Quelle:** CAT-25 / PR #6 · 2026-08-27

---

### Category-Discovery erfindet Duplikate vorhandener Kategorien `💡 Idee`
**Problem:** `category_discovery.py` schlägt neue Kategorien vor, die semantisch
bereits existieren — `Restaurants & Lieferdienste` neben `Essen & Trinken`,
`Tankstelle` neben `Mobilität`, `Baumarkt` und `Strom/Gas` neben `Wohnen`,
`Campingplätze` neben `Urlaub`. Die Auswertung zerfasert, Vergleiche über Monate
brechen, und jede Korrektur ist Handarbeit per SQL.

- **Priorität:** P2 — kostet bei jedem Import Nacharbeit und macht Monatsvergleiche
  unbrauchbar, korrumpiert aber keine Beträge. P1, sobald jemand den Kategorien im
  Dashboard ohne Nachkontrolle vertraut.
- **Auslöser:** CAT-25-Import erzeugte 11 neue Kategorien in einem Lauf. Auch **nach**
  dem Seeding-Fix (PR #6), als der Prompt die vollständige kanonische Liste sah, kamen
  noch `Baumarkt`, `Tankstelle` und `Campingplätze` dazu — der unvollständige Prompt war
  also nur die halbe Ursache.
- **Scope:** Prompt in `_DISCOVERY_SYSTEM` verschärfen (explizit gegen Untermengen
  vorhandener Kategorien) und den Vorschlag serverseitig gegen `CATEGORIES` prüfen,
  statt ihn ungefiltert zu übernehmen. Optional: Discovery per Flag abschaltbar.
- **Größe:** S · **Quelle:** CAT-25 / PR #6 · 2026-08-27

---

### PayPal-Sammellastschriften automatisch aufschlüsseln `💡 Idee`
**Problem:** Auf dem Girokonto ist jede PayPal-Zahlung nur „PayPal (Europe) S.a r.l."
in der Kategorie `PayPal`. Der echte Empfänger steht in der PayPal-CSV und lässt sich
über den Transaktionscode zuordnen — passiert aber nicht automatisch.

- **Priorität:** P2 — betrifft rund 1.935 € über drei Monate, die als undifferenzierter
  Block dastehen. Kein Datenverlust, aber der Bucket wächst mit jedem Monat.
- **Auslöser:** Mai (alter CSV-Import) hat die PayPal-Lastschriften auf echte Kategorien
  aufgeschlüsselt (Shopping, Abonnements, Mobilität), Juni/Juli liegen flach in `PayPal`.
  Die Kategoriezeile ist dadurch zwischen den Monaten nicht vergleichbar.
- **Scope:** Beim Import einer PayPal-CSV die Giro-Lastschriften über Betrag+Datum
  matchen und die Kategorie des echten Empfängers übernehmen. Der manuelle
  SQL-Workaround ist in der Projekt-Memory dokumentiert. Nicht im Scope: Kreditkarte
  (dort ist der Händler bereits im Auszug).
- **Größe:** M · **Quelle:** CAT-25 / PR #6 · 2026-08-27

---

### Überlappende Auszugszeiträume beim Upload erkennen `💡 Idee`
**Problem:** `dedup_hash` ist `SHA-256(datum|merchant.lower()|betrag)` und damit vom
Händlerstring abhängig. Derselbe Monat aus zwei Formaten (CSV-Export vs. PDF-Auszug)
schreibt denselben Umsatz zweimal in die DB, weil die Schreibweise minimal abweicht.

- **Priorität:** P2 — führt zu still verdoppelten Monaten. Der Nutzer merkt es erst an
  unplausiblen Summen, und die Bereinigung ist ein manuelles `DELETE` auf `upload_id`.
- **Auslöser:** CAT-25: der Mai-Giro lag als CSV (Upload 7) und als PDF (Upload 8) vor,
  126 vs. 123 Buchungen, identischer Zeitraum 04.05.–29.05. Nur 7 Duplikate wurden
  erkannt, die restlichen 116 nicht.
- **Scope:** `dedup_hash` bleibt unverändert (unveränderliche Regel in `CLAUDE.md`).
  Stattdessen beim Upload den Datumsbereich gegen bestehende Uploads prüfen und bei
  Überlappung warnen bzw. rückfragen. Nicht im Scope: Merchant-Fuzzy-Matching.
- **Größe:** S · **Quelle:** CAT-25 / PR #6 · 2026-08-27

---

### Empfänger von Auslandsüberweisungen aus dem Anlagenteil lesen `💡 Idee`
**Problem:** Auslandsüberweisungen erscheinen im Postbank-Auszug nur als
`AUSL.ZAHL. 02PR260710200014KREF+...` — ohne Empfänger. Der steht ausschließlich im
Anlagenteil hinter `Anlagen zum Kontoauszug` (`BEGUENSTIGTER: ... MELNIKOVA OLHA`),
den `pdf_postbank.parse()` bewusst nicht mitliest.

- **Priorität:** P2 — der größte nicht-fixe Ausgabenblock des Quartals (2.314 € über
  drei Monate) landet als anonyme Referenznummer in `Sonstiges`. Kein Fehler, nur blind.
- **Auslöser:** CAT-25: zwei Überweisungen à ~1.150 € mussten über die REF-Nummer von
  Hand zugeordnet werden, um überhaupt zu sehen, an wen sie gingen.
- **Scope:** Anlagenteil separat parsen, REF-Nummer aus der Buchung gegen die Belege
  matchen und Empfänger + Originalbetrag/Wechselkurs in die `description` schreiben.
  Der Anlagenteil bleibt weiterhin keine Quelle für Buchungen.
- **Größe:** S · **Quelle:** CAT-25 / PR #6 · 2026-08-27

---

### `test_history_integrity` von der Produktions-DB lösen `💡 Idee`
**Problem:** Die zehn Tests in `backend/tests/test_history_integrity.py` laufen gegen
die echte `backend/cut_the_fat.db`. In jedem frischen Worktree und in CI gibt es die
nicht — die Tests scheitern mit `no such table: transactions`.

- **Priorität:** P2 — hält die Suite dauerhaft rot, wo kein DB-File liegt, und
  verdeckt damit echte Regressionen. P1, sobald die Suite in CI laufen soll.
- **Auslöser:** Baseline-Check im CAT-25-Run: 10 rote Tests im Worktree, dieselben
  10 grün gegen die echte DB.
- **Scope:** Fixture, die eine temporäre SQLite-DB anlegt und mit einem kleinen,
  bekannten Datensatz füllt (Muster wie in `test_category_seeding.py`, `NullPool`
  wegen der Event-Loop-Wechsel). Die Integritätslogik selbst bleibt unverändert.
- **Größe:** S · **Quelle:** CAT-25 / PR #6 · 2026-08-27

---

### Abrechnungszeitraum von Kreditkartenauszügen berücksichtigen `💡 Idee`
**Problem:** easybank-Kreditkartenabrechnungen haben Stichtag Monatsanfang. Die
Abrechnung „vom 2. Juni 2026" enthält die **Mai**-Umsätze. Wer nach Dateidatum oder
Abrechnungsmonat sortiert, ordnet sie dem falschen Monat zu.

- **Priorität:** P3 — die einzelnen Buchungsdaten sind korrekt, nur die Erwartung
  „drei Auszüge = drei Monate" stimmt nicht. Wird P2, wenn das Dashboard je nach
  Abrechnung statt nach Buchungsdatum gruppiert.
- **Auslöser:** CAT-25 fragte nach Mai–Juli; die drei beigefügten Kartenabrechnungen
  deckten April–Juni ab, die Juli-Umsätze fehlten komplett (August-Abrechnung).
- **Scope:** `Abrechnungszeitraum: TT.MM.JJJJ - TT.MM.JJJJ` aus dem Auszug lesen und
  beim Upload anzeigen, damit Lücken sichtbar werden.
- **Größe:** S · **Quelle:** CAT-25 / PR #6 · 2026-08-27

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
