# Cut the Fat — Tauri Desktop App

## Überblick

Die Desktop-App verpackt die bestehende Web-UI (Chat + Finanzanalyse) als
native Anwendung für macOS, Linux und Windows. Technologie: **Tauri 2** (Rust-
Shell, ~5 MB) mit dem Python-Backend als **PyInstaller-Sidecar**.

Die CLI (`./ctf`) bleibt parallel verfügbar und wird nicht verändert.

```
┌───────────────────────────────────────────────┐
│  Tauri Shell (Rust, ~5 MB)                    │
│  ┌─────────────────────────────────────────┐  │
│  │  System-WebView (HTML/CSS/JS)           │  │
│  │  web/static/ — Chat-Oberfläche          │  │
│  │  verbindet via ws://localhost:PORT       │  │
│  └──────────────┬──────────────────────────┘  │
│                 │                              │
│  ┌──────────────▼──────────────────────────┐  │
│  │  Python Sidecar (PyInstaller-Binary)    │  │
│  │  FastAPI + WebSocket + SQLite           │  │
│  │  Kategorisierer, Insights, Parser       │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  Plugins: shell, dialog, process              │
└───────────────────────────────────────────────┘
```

## Schnellstart

### Voraussetzungen

| Tool        | Version | Installation                                          |
|-------------|---------|------------------------------------------------------|
| Rust        | stable  | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Node.js     | >= 18   | https://nodejs.org                                    |
| Python      | >= 3.12 | System oder pyenv                                     |
| PyInstaller | latest  | `pip install pyinstaller`                             |

**Linux (zusätzlich):**
```bash
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
```

**macOS:** Xcode Command Line Tools (`xcode-select --install`)

### Setup

```bash
# 1. Python venv einrichten (falls noch nicht vorhanden)
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pyinstaller
cd ..

# 2. .env-Datei anlegen
cp .env.example .env
# ANTHROPIC_API_KEY eintragen (optional, für KI-Features)
```

### Starten

```bash
# Komplett-Start (baut Sidecar + startet Tauri dev)
./ctf-desktop

# Ohne Sidecar-Neubauen (wenn Binary schon vorhanden)
./ctf-desktop --skip-build

# Release-Bundle erstellen
./ctf-desktop --release
```

## Wie es funktioniert

### Ablauf beim Start

1. **`./ctf-desktop`** prüft Voraussetzungen (Rust, Node, Python venv)
2. **PyInstaller** baut `web/app.py` als Single-Binary → `dist/ctf-sidecar`
3. **rename-sidecar.mjs** kopiert das Binary mit Target-Triple-Suffix nach
   `src-tauri/binaries/ctf-sidecar-<triple>` (z.B. `ctf-sidecar-x86_64-unknown-linux-gnu`)
4. **`npx tauri dev`** startet die Tauri-App:
   - Tauri findet einen freien Port via `portpicker`
   - Spawnt den Python-Sidecar mit Port als Argument
   - Python startet uvicorn, gibt `READY:8765` auf stdout aus
   - Rust fängt das READY-Signal ab und speichert den Port
5. **WebView** öffnet `web/static/index.html`
6. **JavaScript** erkennt Tauri-Umgebung (`window.__TAURI_INTERNALS__`)
7. **`invoke('get_backend_port')`** holt den Port vom Rust-Layer
8. **WebSocket** verbindet zu `ws://localhost:8765/ws/chat`
9. Ab hier funktioniert alles wie in der Web-UI

### Port-Discovery

Der Port wird **nicht** hardcoded. Jede Instanz bekommt einen zufälligen
freien Port. Das verhindert Konflikte, wenn mehrere Instanzen laufen.

Sequenz:
```
Rust                    Python Sidecar           Frontend (JS)
  │                         │                        │
  │── spawn(port=8765) ────▶│                        │
  │                         │── uvicorn.startup() ──▶│
  │                         │── print("READY:8765")  │
  │◀── stdout capture ─────│                        │
  │                         │                        │
  │                         │          invoke('get_backend_port')
  │◀─────────────────────────────────────────────────│
  │── return 8765 ──────────────────────────────────▶│
  │                         │          ws://localhost:8765/ws/chat
  │                         │◀───────────────────────│
```

### Dual-Mode Frontend

`chat.js` erkennt automatisch, ob es in Tauri oder im Browser läuft:

- **Tauri-Modus:** Port via IPC (`invoke`), URLs zu `localhost:PORT`
- **Browser-Modus:** Gleicher Origin, relative URLs

Dadurch funktioniert `./ctf-web` (standalone Web-UI) weiterhin.

## Dateistruktur (neue/geänderte Dateien)

```
cut-the-fat/
├── ctf-desktop                       # ← Startscript (NEU)
├── scripts/
│   ├── build-sidecar.mjs             # PyInstaller-Wrapper (NEU)
│   └── rename-sidecar.mjs            # Target-Triple-Rename (NEU)
├── src-tauri/                        # ← Tauri Rust-Layer (NEU)
│   ├── Cargo.toml                    # Rust-Dependencies
│   ├── tauri.conf.json               # App-Konfiguration
│   ├── build.rs                      # Tauri Build-Script
│   ├── capabilities/
│   │   └── default.json              # Sidecar-Permissions
│   ├── binaries/
│   │   └── .gitkeep                  # Sidecar-Binaries (gebaut, nicht committed)
│   └── src/
│       ├── main.rs                   # Entry point
│       └── lib.rs                    # Sidecar-Startup + IPC
├── web/
│   ├── app.py                        # ← GEÄNDERT: CORS, __main__, Port-Arg
│   ├── handlers/
│   │   └── bugreport.py              # ← NEU: GitHub Issues API
│   └── static/
│       ├── index.html                # ← GEÄNDERT: Bug-Report-Button + Modal
│       └── chat.js                   # ← GEÄNDERT: Tauri-Erkennung, Port-IPC
├── .github/workflows/
│   └── release.yml                   # ← NEU: CI/CD für Desktop-Release
├── backend/requirements.txt          # ← GEÄNDERT: +httpx
└── .gitignore                        # ← GEÄNDERT: +Tauri/PyInstaller
```

## Build & Release

### Lokaler Build

```bash
# Entwicklungsmodus (hot-reload für Frontend)
./ctf-desktop

# Release-Bundle
./ctf-desktop --release
# Ergebnis: src-tauri/target/release/bundle/
#   Linux: .deb + .AppImage
#   macOS: .dmg + .app
#   Windows: .msi + .exe
```

### CI/CD (GitHub Actions)

Der Workflow `.github/workflows/release.yml` wird bei Tags (`v*`) getriggert:

1. **Stage 1:** Baut Sidecar auf allen 3 Plattformen (PyInstaller Matrix)
2. **Stage 2:** Baut Tauri-App, paketiert als .deb/.AppImage/.dmg/.msi
3. Erstellt automatisch einen GitHub Release (Draft)

Benötigte Secrets:
- `TAURI_SIGNING_PRIVATE_KEY` — für Auto-Updater-Signatur
  ```bash
  cargo tauri signer generate -w ~/.tauri/cutthefat.key
  ```

### Manueller Sidecar-Build

Falls du nur den Python-Sidecar testen willst:

```bash
# Bauen
node scripts/build-sidecar.mjs

# Für Tauri umbenennen
node scripts/rename-sidecar.mjs

# Direkt testen (ohne Tauri)
./dist/ctf-sidecar 8080
# → "READY:8080" auf stdout, dann http://localhost:8080
```

## Bug-Report-System

In der Desktop-App gibt es einen 🐛-Button (unten rechts):

1. Klick öffnet ein Modal mit Titel, Beschreibung, Reproduktionsschritte
2. Die letzten 50 Chat-Nachrichten werden automatisch als Kontext angehängt
3. POST an `/api/bugreport` → erstellt ein GitHub Issue via API
4. Benötigt `GITHUB_TOKEN` in der `.env`

Im Browser-Modus ist der Button ausgeblendet.

## Bekannte Einschränkungen

- **Kein Apple Code Signing** — macOS-Nutzer müssen beim ersten Start
  Rechtsklick → Öffnen verwenden (Gatekeeper-Warnung)
- **PyInstaller-Binaries** sind 50-80 MB groß (Python + alle Dependencies)
- **Kein Auto-Updater** konfiguriert — `plugins.updater.pubkey` in
  `tauri.conf.json` muss noch mit generiertem Key befüllt werden
- **Windows Antivirus** kann PyInstaller-Binaries als verdächtig flaggen

## Nächste Schritte (Phase 2-4)

- [ ] Auto-Updater: Signing-Keys generieren, `pubkey` eintragen
- [ ] Crash-Reporting: Sentry-Integration (Python-Seite)
- [ ] Structured Logging: Logfile in App-Data-Verzeichnis
- [ ] WebSocket-Reconnect: Exponential Backoff bei Verbindungsabbruch
- [ ] App-Data-Pfade: `platformdirs` für DB + Logs (statt Projektverzeichnis)
