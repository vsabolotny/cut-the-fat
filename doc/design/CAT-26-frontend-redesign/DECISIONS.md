# CAT-26 — Frontend-Redesign: Analyse & Entscheidungen

**Ziel (aus dem Ticket):** Maximaler Fokus darauf, dass der Nutzer seinen Geldfluss anhand der Transaktionen klar und einfach verfolgen kann. Alles andere darf versteckt oder anders gelöst werden.

**Deliverables:** [`prototype.html`](prototype.html) (3 Varianten, umschaltbar oben rechts, komplett eigenständig — per Doppelklick im Browser öffnen) + dieses Dokument.

---

## 1. Analyse der heutigen UI — was konkurriert mit dem Geldfluss?

Grundlage: `web/static/index.html`, `transactions.html`, `chat.js`, `style.css` (Stand `main`, b9740df).

| # | Befund | Beleg | Problem |
|---|--------|-------|---------|
| 1 | **Chat-first-Architektur invertiert die Prioritäten.** Beim Laden zeigt die Datenfläche eine Willkommenskarte mit 6 Quick-Buttons — null Daten. | `index.html:61–90` | Jede Information kostet mindestens eine Interaktion. Der Geldfluss ist das *Ergebnis* einer Chat-Anfrage statt der Ausgangszustand. |
| 2 | **10 permanent sichtbare Filter-Controls** auf der Transaktionsseite: 5 Zeitraum-Pills, 2 Datums-Inputs, Kategorie-Select, Typ-Select, Händlersuche. | `transactions.html:28–68` | Der Standardfall ("dieser/letzter Monat, Ausgaben") braucht genau ein Control. Der Rest ist Dauerlärm. |
| 3 | **6-Spalten-Tabelle mit Metadaten.** "Quelle" ist Provenienz, "Beschreibung" ist roher Banktext, "Datum" wiederholt sich pro Zeile. | `transactions.html:90–97` | Auge muss pro Zeile 6 Spalten scannen, davon tragen 3 nichts zum Geldfluss bei. |
| 4 | **Die Kopfzahl fehlt.** Eingang − Ausgaben = Übrig steht nirgendwo dauerhaft; die Summary-Zeile erscheint nur auf der Transaktionsseite und gefiltert. | `transactions.html:71–84` | Genau die eine Zahl, um die sich "Geldfluss verfolgen" dreht, hat keinen festen Platz. |
| 5 | **3 gleichrangige Seiten** (Chat / Transaktionen / Einstellungen) fragmentieren ein Ein-Themen-Produkt. | `index.html:23–27` | Navigation ist Overhead; Einstellungen sind kein Primärziel. |
| 6 | **26 Kategorien flach** in Selects und Chips. | `transaction.py` (CATEGORIES) | Unlesbar ohne Gruppierung/Top-N. |
| 7 | **Natalie-Kategorien vermischen privat und Business.** Insights schließen sie bereits aus, die UI nicht. | Kategorienliste; bestehende Insights-Regel | Der private Geldfluss ist ohne Trennung nicht ablesbar. |

## 2. Design-These

> **Ein Bildschirm beantwortet ohne Interaktion: "Wohin ist mein Geld diesen Monat geflossen?"**

Daraus folgt die Versteck-Liste:

- **Chat → schwebender Assistent.** Chat bleibt das Werkzeug für Analyse-Fragen ("Wo kann ich sparen?"), wird aber vom Gatekeeper zum Helfer: ein Floating-Button, Panel bei Bedarf. Die Übersicht selbst braucht keinen Chat.
- **Filter → ein Disclosure.** Sichtbar bleibt nur die Monatsnavigation. Typ-Filter und Suche liegen hinter einem "Filter"-Aufklapper; die 5 Zeitraum-Pills und 2 Datums-Inputs entfallen (Monat vor/zurück deckt >90 % ab).
- **Tabelle → Feed.** Spalten "Quelle" und "Beschreibung" raus (Beschreibung bei Bedarf per Klick auf die Zeile). Datum wird zum Tages-Gruppenkopf statt Spalte. Übrig: Händler, Kategorie, Betrag.
- **Einstellungen/Import → stille Links** im Seitenkopf statt gleichrangiger Navigation.
- **Kategorien → Top 6 + "Sonstige"** in Legende und Balken; die volle Liste nur im Bearbeiten-Dialog.
- **Natalie → ein Schalter** ("Natalie ausblenden"), der Summen, Balken und Feed konsistent umrechnet — dieselbe Regel, die Insights schon anwenden.

## 3. Die drei Varianten

### Variante 1 · „Fluss" — Empfehlung

Cash-Flow-first im Vokabular des deutschen Haushaltsbuchs: Papier, Tinte, **rote Zahlen für Ausgaben, schwarze für Eingänge, Grün nur für "Übrig"**. Signaturelement ist die **Schnittleiste**: ein Balken in voller Breite = Eingang des Monats, von links werden die Ausgaben-Kategorien "abgeschnitten", rechts bleibt der grün schraffierte Rest — mit der Schere (dem Produktlogo) am Schnittpunkt. Der Produktname wird damit zum Diagramm: *Cut the Fat* zeigt wörtlich, wo geschnitten wird.

- Drei Kopfzahlen (Eingang / Ausgaben / Übrig) immer sichtbar, Monat zentriert mit ‹ ›.
- Kategorie-Chips unter der Leiste filtern den Feed per Klick.
- Feed nach Tagen gruppiert, Beträge tabellarisch ausgerichtet (`tabular-nums`).
- Assistent als Floating-Button unten rechts.
- "Natalie ausblenden"-Schalter direkt über dem Feed.

**Warum Empfehlung:** setzt die Ticket-Vorgabe am radikalsten um (null Interaktionen bis zur Antwort), und die helle Haushaltsbuch-Anmutung unterscheidet das Produkt von jeder generischen Dark-Dashboard-Finanz-App.

### Variante 2 · „Kontoblatt"

Maximale Datendichte für den Power-User: dunkles Bankiers-Grün-Schwarz, Messing-Akzent, Monospace-Ziffern, **laufender Saldo pro Buchung** — die Information, die keine der heutigen Ansichten bietet. Kein Chart, keine Chips; die Tabelle selbst ist die Visualisierung. Interessant, falls sich herausstellt, dass der tatsächliche Nutzungsmodus "Zeile für Zeile prüfen" ist (Kategorien-Review).

### Variante 3 · „Klassik+"

Bewusste Kontrollgruppe: das heutige Dark-Indigo-Design, aber **nur** mit angewandter Versteck-Liste — Summary-Karten nach oben, eine Filterzeile (Monat + Suche + "Mehr Filter"), 4 statt 6 Spalten, Chat als Nav-Punkt "Assistent" statt Startseite. Zeigt, was Weglassen allein bringt, ohne visuelles Neuland. Fallback mit minimalem Umsetzungsaufwand.

## 4. Entscheidungen im Detail

| Entscheidung | Begründung |
|---|---|
| Rot/Schwarz statt Rot/Grün für Beträge | Deutsche Buchhaltungs-Konvention ("rote/schwarze Zahlen"); Grün bleibt exklusiv dem "Übrig" vorbehalten und behält dadurch Bedeutung. |
| Helles Papier-Thema für die Empfehlung | Die bestehende App nutzt das generischste Dark-Indigo (#6366f1). Ein Haushaltsbuch ist ein Alltagsgegenstand bei Tageslicht; hell + Doppellinie + Schraffur ist eine begründete, wiedererkennbare Abweichung. |
| Schnittleiste statt Donut/Balkendiagramm | Ein Donut zeigt Anteile *der Ausgaben*; die Schnittleiste zeigt Ausgaben *im Verhältnis zum Eingang* — das ist Geldfluss. Und sie trägt die Produktmetapher. |
| Tages-Gruppierung statt Datumsspalte | Datum ist Kontext, kein Vergleichswert; als Gruppenkopf strukturiert es, ohne eine Spalte zu kosten. |
| Beschreibung/Quelle versteckt, nicht gelöscht | Für Kategorien-Review nötig (PayPal-Fall: echter Empfänger steht in der Beschreibung) — gehört in die Zeilen-Detailansicht, nicht in die Liste. |
| Prototyp ohne CDN/Netz | `file://`-öffnbar, kein Chart.js nötig — die Schnittleiste ist reines CSS; hält den Prototyp ehrlich zur späteren CSP (die App pinnt CDN-Hashes). |

## 5. Out of scope

- Keine Änderung an `web/static/` — der Prototyp ist ein Design-Artefakt mit Mock-Daten.
- Umsetzung der gewählten Variante (eigenes Ticket nach Entscheidung).
- Mobile-App, CLI, Desktop-Shell (Tauri) — unverändert.
- Kategorie-Bearbeitungs-Dialog und Import-Flow sind nur als Einstiegspunkte angedeutet.

## 6. Testplan / Verifikation

- `backend/tests/test_design_prototype.py`: Prototyp parst als HTML, enthält alle 3 Varianten und referenziert keine externen Ressourcen (kein `http(s)://`-Load).
- Manuell im Browser verifiziert: Varianten-Umschalter, Schnittleiste, Chip-Filter, Natalie-Schalter, Suche (Fluss + Klassik+), laufender Saldo (Kontoblatt).

## 7. Empfehlung & nächster Schritt

Variante 1 „Fluss" umsetzen; aus Variante 2 den laufenden Saldo als optionale Spalte der Zeilen-Detailansicht übernehmen. Nächster Schritt nach Sichtung: Entscheidung im Ticket kommentieren, dann Umsetzungs-Ticket.
