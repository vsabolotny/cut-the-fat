## UI Plan — Trials, Architektur, nächster Schritt

### Leitplanken (aus PRD + Repo-Constraints)
- **Keine neue HTTP-Schicht im MVP**: Das Repo ist bewusst CLI+Services ohne FastAPI.
- **Keine Funktionsänderungen am bestehenden Code (zuerst)**: Anthropic-Calls bleiben unverändert drin.
- **Transparenz statt Vermeidung (zuerst)**: UI hebt hervor, dass Daten an Anthropic gesendet werden, und zeigt den Payload an.
- **Reuse statt Rewrite**: Bestehende `cli/db.py` + `app/queries` + Services weiterverwenden.

### UI-Optionen (bewusst als “Trials”)
#### Option A — Desktop-App mit embedded Python (empfohlen als Trial 1)
- **Tech**: Tauri/Electron + lokale Python-Runtime (bestehendes venv) über subprocess.
- **Vorteile**: UI fühlt sich “wie App” an; keine Browser-URL; Zugriff auf Filesystem ist einfach.
- **Nachteile**: Packaging/Distribution aufwändig (später lösen).
- **Schnittstelle**: UI ruft `./ctf`-Kommandos auf (oder Python entrypoints) und parst strukturiertes JSON.

#### Option B — Lokale Web-UI (Streamlit/NiceGUI) als schnellster MVP
- **Tech**: Streamlit oder NiceGUI im gleichen Python-Projekt.
- **Vorteile**: Schnell; wenig Glue-Code; Python bleibt first-class.
- **Nachteile**: “App-Gefühl” geringer; läuft im Browser; Deployment/Port-Handling.

### Empfehlung: Trial-Strategie
- **Trial 1 (UI/webappTrial1)**: Lokale Web-UI (Streamlit oder NiceGUI), weil schnell Feedback liefert.
- **Trial 2 (UI/desktopTrial2)**: Desktop wrapper (Tauri/Electron) auf Basis stabiler Commands.

### Was wir im Code dafür vorbereiten sollten (klein & zukunftssicher)
1. **Stabile “UI API” als Python-Funktion/Modul (ohne bestehende Logik zu ändern)**
   - Ein Modul, das die Kernaktionen als Funktionen anbietet (upload, dashboard, insights, learn, report).
   - Output als strukturierte Dicts/JSON, damit UI nicht Terminal-Text parsen muss.
2. **Payload-Transparenz für Anthropic Calls**
   - UI zeigt pro Feature einen klaren Hinweis “sendet Daten an Anthropic”.
   - Klick auf Ausrufezeichen öffnet Detailansicht mit **pretty-printed JSON** (bzw. exakt formatiertem Prompt-Inhalt) des zu sendenden Payloads.
   - Ziel: Der Nutzer versteht “was geht raus”, ohne den Code lesen zu müssen.
3. **Deterministische Outputs**
   - Konsistente Datenstrukturen für UI (z.B. `get_summary`, `get_history`, `get_insights_data`).

### Branching-Konvention
- **`UI/webappTrial1`**: Schnellster UI-Prototyp (lokale Web-UI) ohne Änderungen an bestehender Business-Logik; UI darf nur “drumherum” bauen (Transparenz, Darstellung, Triggern der bestehenden Flows).
- **`UI/desktopTrial2`**: Desktop-Wrapping/Packaging, wenn Trial 1 den Funktionsumfang validiert.

### “Definition of Done” für Trial 1
- Upload über UI (File picker) funktioniert.
- Dashboard zeigt letzten Monat + Auswahl.
- Insights anzeigen + “Neu generieren” Button.
- Learn: uncategorized merchants → Kategorie auswählen → Regel speichern.
- UI zeigt sichtbar, wenn ein Flow **Daten an Anthropic sendet**, inkl. Detailansicht (Ausrufezeichen) mit dem übertragenen Payload (formatiert).

