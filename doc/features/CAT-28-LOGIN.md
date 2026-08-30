# CAT-28 — Login-Gate für Web- und Desktop-App

## Kontext

Die App zeigt Kontoauszüge, Händler und Beträge — die sensibelsten Daten, die ein
Haushalt hat. Aktuell ist jede Seite ohne jede Hürde erreichbar: Wer den Rechner
entsperrt vorfindet oder den Tab offen sieht, sieht alles. `web/auth.py` schützt
heute nur die Strecke Tauri ↔ Sidecar (`CTF_AUTH_TOKEN`) — das ist ein
Maschinen-zu-Maschinen-Gate, kein Nutzer-Login.

Vorbild laut Ticket: drinkwise (`~/Projects/vlads/drinkwise`). Dort gilt:
Passwort-Hash in der DB, Bearer-Token nach dem Login, Frontend-Login-Seite vor
der App, `GET /api/auth/me` als Session-Check, 401 → zurück zum Login.

## Produktziele

1. Ohne gültige Session ist keine Seite und kein `/api/*`-Endpunkt der App erreichbar.
2. Beim ersten Start legt der Nutzer einmalig ein Passwort fest (kein Default-Passwort).
3. Session überlebt einen Reload, läuft aber nach 12 Stunden ab.
4. Funktioniert unverändert in beiden Modi: Browser (`./ctf-web`) und Tauri-Desktop.

## Nicht-Ziele

- **Mehrbenutzer-Betrieb.** Die `users`-Tabelle ist auf genau einen Datensatz
  ausgelegt; Familien-Konten sind Roadmap-Phase 6.
- **Passwort-Reset per E-Mail.** Lokale App ohne Mailversand; Reset erfolgt
  bewusst über das Löschen des Nutzerdatensatzes (dokumentiert, nicht als UI).
- **CLI-Absicherung.** `./ctf` läuft in der Shell des Nutzers und greift direkt
  auf die SQLite-Datei zu; ein Login davor wäre Theater.
- **Registrierung mehrerer Konten, Rollen, Admin-Bereich.**

## UX / Verhalten

**Erststart (kein Nutzer in der DB)**
`/login` zeigt "Passwort festlegen" mit zwei Feldern (Passwort + Wiederholung),
mindestens 8 Zeichen. Nach dem Anlegen ist der Nutzer sofort eingeloggt und
landet auf `/`.

**Normaler Start**
`/login` zeigt ein Passwortfeld. Falsches Passwort → deutsche Fehlermeldung,
kein Hinweis darauf, ob überhaupt ein Konto existiert. Erfolg → `/`.

**Eingeloggt**
Topbar bekommt rechts einen "Abmelden"-Button. Klick verwirft das Token und
führt zurück auf `/login`.

**Abgelaufene Session**
Jeder `apiFetch`, der 401 zurückbekommt, verwirft das Token und leitet auf
`/login?expired=1` — dort steht "Sitzung abgelaufen, bitte erneut anmelden."

## Technischer Ansatz

### Token-Mechanik: signiert mit der Standardbibliothek statt JWT

Drinkwise nutzt `python-jose` + `passlib[bcrypt]`. Beides wird hier **bewusst
nicht** übernommen: Der Sidecar wird per PyInstaller zur Single-Binary gebaut,
und `bcrypt`/`cryptography` sind native Extensions — zusätzliche ~15 MB plus die
bekannteste Fehlerquelle beim Sidecar-Build, für ein Ein-Nutzer-Gate auf
127.0.0.1.

Stattdessen, gleiche Sicherheitseigenschaften, keine neuen Abhängigkeiten:

- **Passwort-Hash:** `hashlib.scrypt` (n=2^14, r=8, p=1) mit 16-Byte-Salt,
  gespeichert als `scrypt$n$r$p$<salt-b64>$<hash-b64>`. Speicherhartes KDF,
  in der Standardbibliothek, Vergleich über `hmac.compare_digest`.
- **Session-Token:** `<payload-b64>.<hmac-sha256-b64>` über
  `{"sub": <user-id>, "exp": <unix-ts>}` — dieselbe Form wie ein JWT, nur ohne
  Header-Segment und ohne Fremdbibliothek. Signaturprüfung vor dem Parsen.
- **Signaturschlüssel:** 32 zufällige Bytes in `.ctf-session-secret` im
  Projektwurzelverzeichnis (Mode 0600, gitignored), beim ersten Bedarf erzeugt.
  Analog zu `.ctf-profile.json`. Wird die Datei gelöscht, sind alle Sessions
  ungültig — das ist die dokumentierte Notbremse.

Die Trennung liegt in `web/session.py`, damit ein späterer Wechsel auf echtes
JWT ein Austausch von zwei Funktionen ist.

### Datenmodell

`backend/app/models/user.py` → Tabelle `users`:
`id`, `username` (unique, Default `"owner"`), `password_hash`, `created_at`,
`last_login_at`. Registriert in `queries.ensure_initialized()` (create_all) und
zusätzlich als Alembic-Migration `0004_add_users_table`.

### Endpunkte (`web/handlers/auth_api.py`)

| Route | Auth | Zweck |
|---|---|---|
| `GET /api/auth/status` | offen | `{"setup_required": bool}` — steuert, welches Formular `/login` zeigt |
| `POST /api/auth/setup` | offen, nur solange kein Nutzer existiert | Legt den einzigen Nutzer an, gibt Token zurück |
| `POST /api/auth/login` | offen | Passwortprüfung → Token |
| `GET /api/auth/me` | Session | Session-Check fürs Frontend |
| `POST /api/auth/logout` | Session | No-op serverseitig (stateless), fürs Frontend symmetrisch |

### Gate (`web/auth.py`, neue `LoginRequiredMiddleware`)

Läuft **innerhalb** der bestehenden `AuthMiddleware`, damit das Sidecar-Token
weiterhin die äußere Schranke bleibt und beide Ebenen unabhängig gelten.

Geschützt:
- alle `/api/*` außer den vier offenen Auth-Routen,
- die Seitenrouten `/`, `/transactions`, `/settings`,
- **jede `*.html` aus dem Static-Mount außer `login.html`** — ohne diese Regel
  liefert `GET /index.html` die App am Gate vorbei, weil `StaticFiles` auf `/`
  gemountet ist.

Nicht geschützt: `style.css`, `*.js`, `/login`, `/login.html`. Diese Dateien
enthalten keine Nutzerdaten und werden für die Login-Seite selbst gebraucht.

Antwortverhalten: `/api/*` → `401 JSON`. Seitenaufrufe → `303` auf `/login`,
damit ein Deep-Link im Browser nicht als roher JSON-Fehler landet.

WebSocket `/ws/chat`: prüft zusätzlich zum Sidecar-Token einen
`?session=`-Parameter und schließt mit Code 1008, wenn er fehlt oder abgelaufen ist.

### Frontend

- `web/static/login.html` + `login.js` — eigenständige Seite im bestehenden
  Stil, ohne Topbar, mit den beiden Formularvarianten.
- `topbar.js`: `apiFetch` hängt `Authorization: Bearer <token>` an (Token aus
  `localStorage`, Schlüssel `ctf_session`), `wsUrl` hängt `session=` an, und ein
  401 aus `apiFetch` löst den Redirect auf `/login?expired=1` aus.

Das bestehende Dual-Mode-Pattern (Tauri vs. Browser) bleibt unverändert:
Der Session-Token liegt zusätzlich zum, nicht anstelle des, `X-CTF-Token`.

## Akzeptanzkriterien

1. Frische DB → `GET /` leitet auf `/login`, das Setup-Formular erscheint.
2. Passwort < 8 Zeichen → 400, kein Nutzer angelegt.
3. Nach Setup existiert genau ein Nutzer; ein zweiter `POST /api/auth/setup` → 409.
4. Falsches Passwort → 401, identische Meldung wie bei nicht existierendem Nutzer.
5. `GET /api/transactions` ohne Token → 401; mit gültigem Token → 200.
6. `GET /index.html` ohne Token → 303 auf `/login` (nicht die App).
7. `GET /style.css` ohne Token → 200.
8. Token mit `exp` in der Vergangenheit → 401.
9. Token mit manipuliertem Payload (gültiges Base64, falsche Signatur) → 401.
10. Sidecar-Modus: gültiger Session-Token, aber fehlendes `X-CTF-Token` → weiterhin 401.

## Testplan

`backend/tests/test_auth_login.py`, ohne echte DB (die Passwort- und
Token-Funktionen sind rein), plus Middleware-Tests über `fastapi.testclient`
gegen eine temporäre SQLite-Datei:

- scrypt: Hash ≠ Klartext, Verify true/false, Format-Roundtrip, kaputter Hash → False
- Token: Roundtrip, abgelaufen, falsche Signatur, Müll-Eingabe, fehlendes Segment
- Middleware: die Akzeptanzkriterien 5–10 als Requests
- Setup-Flow: erster Setup 201, zweiter 409, zu kurzes Passwort 400
