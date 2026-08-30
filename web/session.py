"""Passwort-Hashing und Session-Tokens für den Nutzer-Login (CAT-28).

Bewusst ohne Fremdbibliotheken: Der Sidecar wird per PyInstaller zur
Single-Binary gebaut, und `bcrypt`/`cryptography` sind native Extensions.
`hashlib.scrypt` und `hmac` aus der Standardbibliothek liefern für ein
Ein-Nutzer-Gate auf 127.0.0.1 dieselben Eigenschaften.

Der Token hat die Form `<payload-b64>.<signatur-b64>` — dieselbe Struktur wie
ein JWT ohne Header-Segment. Wer später auf echtes JWT wechseln will, tauscht
`create_token` und `verify_token` aus; der Rest des Codes kennt nur Strings.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

# Die Geheimnisdatei liegt neben `.ctf-profile.json` im Projektwurzelverzeichnis.
SECRET_FILE = Path(__file__).resolve().parent.parent / ".ctf-session-secret"

TOKEN_TTL_SECONDS = 12 * 60 * 60
MIN_PASSWORD_LENGTH = 8

# Derselbe Token liegt zusätzlich in einem Cookie. Grund: Seitenaufrufe sind
# normale Dokument-Navigationen — der Browser kann dabei keinen
# `Authorization`-Header setzen, das Gate würde also jeden Login sofort wieder
# auf /login zurückwerfen. Der Header bleibt für `fetch` und den WebSocket.
COOKIE_NAME = "ctf_session"

# scrypt-Parameter. n muss eine Zweierpotenz sein; 2^14 kostet ~100 ms und
# ~16 MB pro Prüfung — genug, um Offline-Rateangriffe auf den Hash teuer zu
# machen, ohne den Login spürbar zu verzögern.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


# ---------------------------------------------------------------------------
# Signaturschlüssel
# ---------------------------------------------------------------------------


def get_secret() -> bytes:
    """Lies den Signaturschlüssel, erzeuge ihn beim ersten Aufruf.

    Der Schlüssel liegt als Hex-Text in der Datei, nicht als Rohbytes. Grund:
    Ein Zeilenumbruch, den irgendein Editor oder Deploy-Skript anhängt, muss
    weggeschnitten werden können — und `strip()` auf Rohbytes frisst dabei
    still die zufälligen Bytes, die zufällig Whitespace sind (0x09, 0x0a, 0x20,
    …). Das trifft rund jeden zwanzigsten Schlüssel und macht dann *jeden*
    ausgegebenen Token ungültig. Hex kennt kein Whitespace.

    Wird die Datei gelöscht, sind alle ausgegebenen Tokens ungültig — das ist
    die dokumentierte Notbremse, falls ein Token abhandenkommt.
    """
    if SECRET_FILE.exists():
        try:
            existing = bytes.fromhex(SECRET_FILE.read_text(encoding="ascii").strip())
        except (ValueError, UnicodeDecodeError):
            # Unlesbare Datei: neu erzeugen statt die App unbenutzbar zu
            # lassen. Kostet den Nutzer eine erneute Anmeldung.
            existing = b""
        if existing:
            return existing

    secret = secrets.token_bytes(32)
    # Beim Anlegen direkt auf 0600, damit der Schlüssel nie kurzzeitig
    # welt-lesbar auf der Platte liegt.
    fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, secret.hex().encode("ascii"))
    finally:
        os.close(fd)
    return secret


# ---------------------------------------------------------------------------
# Passwörter
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hashe ein Passwort als `scrypt$n$r$p$<salt>$<hash>`."""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_BYTES,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(derived)}"


def verify_password(password: str, stored: str) -> bool:
    """Prüfe ein Passwort gegen einen gespeicherten Hash.

    Ein kaputter oder fremdformatiger Hash gilt als "passt nicht" — ein
    beschädigter Datensatz darf niemanden einloggen und darf auch nicht mit
    einer Exception den Login-Endpunkt in einen 500er kippen.
    """
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64d(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64d(hash_b64)),
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(derived, _b64d(hash_b64))


# ---------------------------------------------------------------------------
# Session-Tokens
# ---------------------------------------------------------------------------


def create_token(user_id: int, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
    """Erzeuge einen signierten Token für `user_id`."""
    payload = json.dumps(
        {"sub": user_id, "exp": int(time.time()) + ttl_seconds},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = _b64e(payload)
    signature = hmac.new(get_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64e(signature)}"


def verify_token(token: str) -> int | None:
    """Gib die user_id zurück, wenn der Token gültig und nicht abgelaufen ist.

    Die Signatur wird geprüft, *bevor* der Payload geparst wird — sonst würde
    der JSON-Parser auf unsignierte Angreiferdaten losgelassen.
    """
    if not token or token.count(".") != 1:
        return None

    encoded, provided = token.split(".")
    expected = hmac.new(get_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(_b64d(provided), expected):
            return None
        payload = json.loads(_b64d(encoded))
    except (ValueError, TypeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("exp"), int) or payload["exp"] <= time.time():
        return None
    user_id = payload.get("sub")
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        return None
    return user_id


def password_problem(password: str) -> str | None:
    """Gib eine deutsche Fehlermeldung zurück, wenn das Passwort untauglich ist."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein."
    return None
