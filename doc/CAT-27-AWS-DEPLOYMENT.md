# CAT-27 — Web-App online auf AWS (CloudFront, ohne Domain)

## Ziel

Die Web-UI (`web/`) öffentlich erreichbar machen — wie bei DrinkWise Phase 1:
kein eigener Domainname, HTTPS über das Standard-CloudFront-Zertifikat, Zugriff
über `https://<dist-id>.cloudfront.net`.

## Architektur

Anders als DrinkWise (SPA in S3 + API auf EC2) liefert hier **ein** FastAPI-Prozess
alles: statische Seiten, `/api/*` und den WebSocket `/ws/chat`. Deshalb genügt
**eine Origin**:

```
Browser ──HTTPS──> CloudFront (Standard-Cert, CachingDisabled, AllViewerExceptHostHeader)
                        │ HTTP :80 (Security Group: nur CloudFront origin-facing Prefix-List)
                        ▼
                  EC2 t3.small (AL2023, eu-central-1, Elastic IP)
                  docker compose: 1 Container (uvicorn web.app:app :8000 → Host :80)
                  Volumes: SQLite-DB + data/ (persistieren Redeploys)
```

- Region `eu-central-1`, AWS-Account 456359847368 (`--profile drinkwise`).
- Kein S3, kein ALB, kein Lambda. SQLite bleibt (Projektregel) → genau 1 Instanz.
- Secrets in SSM Parameter Store unter `/ctf/prod/*`, beim Deploy nach `.env`
  gespült (`deploy/refresh-env.sh`, Muster von DrinkWise übernommen).

## Sicherheit (Voraussetzung fürs Online-Gehen)

Standalone-Modus hat **keinerlei Auth** — für persönliche Finanzdaten im
Internet inakzeptabel. Neu:

1. **Cookie-Auth-Modus** (`CTF_COOKIE_AUTH=1`, nur im Cloud-Deploy gesetzt):
   - *Alle* Pfade (Seiten, Statics, `/api/*`, WS-Handshake) verlangen den Token.
   - Erstzugriff `https://…/?token=<CTF_AUTH_TOKEN>` → Set-Cookie
     (`ctf_token`, HttpOnly, Secure, SameSite=Lax) + Redirect auf saubere URL.
   - Danach: Cookie reicht (Browser-JS bleibt unverändert, same-origin).
   - `/api/*` akzeptiert weiterhin `X-CTF-Token`-Header, WS weiterhin `?token=`.
2. **Tauri/Desktop unverändert:** ohne `CTF_COOKIE_AUTH` gilt exakt das alte
   Verhalten (nur `/api/*` + WS gated, Seiten offen).
3. **Upload-Fix:** `file.filename` wird auf den Basenamen reduziert
   (Path-Traversal in `web/app.py:228`).
4. **Fail-closed:** Das Image setzt `ENV CTF_COOKIE_AUTH=1`; fehlt dann
   `CTF_AUTH_TOKEN`, bricht `web/app.py` beim Start ab statt ungeschützt zu
   starten. `deploy/refresh-env.sh` überschreibt die `.env` außerdem nur, wenn
   der Token wirklich aus SSM kam. Grund: eine leere `.env` hätte sonst
   sämtliche Auth stillschweigend deaktiviert.
5. **Container läuft als non-root** (`uid 10001`), nur `/data` und
   `/opt/ctf/data` sind beschreibbar.

### Bekannte Einschränkung

Der Login-Link enthält den Token als Query-Parameter — er landet damit in den
uvicorn-Access-Logs der Instanz (im Browser nicht: der 303-Redirect entfernt
ihn sofort). Für einen Single-User-Deploy akzeptiert; Rotation via SSM +
`deploy/deploy.sh`. CloudFront-Access-Logs sind bewusst nicht aktiviert.

## Deploy-Artefakte (im Repo)

| Datei | Zweck |
|---|---|
| `deploy/Dockerfile` | python:3.12-slim, backend/ + web/ + cli/, uvicorn :8000 |
| `docker-compose.prod.yml` | 1 Service, Port 80→8000, `env_file: .env`, Volumes `ctf-db`, `ctf-data` |
| `deploy/provision-aws.sh` | Einmaliges Provisioning: SG, Instance Profile, EC2, EIP, CloudFront |
| `deploy/ec2-bootstrap.sh` | User-Data: docker+git installieren, Repo klonen, refresh-env, compose up |
| `deploy/refresh-env.sh` | SSM `/ctf/prod/*` → `/opt/ctf/.env` (atomisch, mode 600) |
| `deploy/deploy.sh` | Redeploy per `aws ssm send-command` (kein SSH) |
| `doc/CAT-27-AWS-DEPLOYMENT.md` | dieses Dokument + Betriebs-Runbook |

DB-Pfad im Container via `DATABASE_URL=sqlite+aiosqlite:////data/cut_the_fat.db`
(Volume), Uploads via Volume auf `data/`.

## AWS-Ressourcen

Alles Weitere legt **ein** Befehl an (idempotent, mehrfach ausführbar):

```bash
deploy/provision-aws.sh
```

Er erzeugt Security Group (`ctf-web-sg`, Ingress 80 nur von der Prefix-List
`com.amazonaws.global.cloudfront.origin-facing`), Instance Profile
`ctf-ec2-profile`, EC2 `t3.small` (AL2023, User-Data =
`deploy/ec2-bootstrap.sh`), Elastic IP und die CloudFront-Distribution
(Origin = Public-DNS der Elastic IP, HTTP-only, Default-Behavior ALL methods,
`CachingDisabled`, `AllViewerExceptHostHeader`, redirect-to-https) — und gibt
am Ende die URL plus den Login-Link mit Token aus.

### Status (Stand: 2026-08-30)

Bereits angelegt (Account 456359847368, `eu-central-1`):

- IAM-Rolle `ctf-ec2-role`
- SSM-Parameter `/ctf/prod/CTF_AUTH_TOKEN` (SecureString, generiert),
  `/ctf/prod/CTF_COOKIE_AUTH=1`,
  `/ctf/prod/DATABASE_URL=sqlite+aiosqlite:////data/cut_the_fat.db`

Offen — erledigt `deploy/provision-aws.sh`: Security Group, Instance Profile,
EC2, Elastic IP, CloudFront.

Optional vorher, sonst laufen die KI-Features im Regel-Fallback:

```bash
aws ssm put-parameter --profile drinkwise --region eu-central-1 \
  --name /ctf/prod/ANTHROPIC_API_KEY --type SecureString \
  --value "<key>" --overwrite
```

Login-Token jederzeit abrufbar:

```bash
aws ssm get-parameter --profile drinkwise --region eu-central-1 \
  --name /ctf/prod/CTF_AUTH_TOKEN --with-decryption \
  --query Parameter.Value --output text
```

## Out of scope

- Eigene Domain / ACM / Route53 (DrinkWise Phase 2, separates Ticket).
- GitHub-Actions-Auto-Deploy bei Push auf main (Backlog; Redeploy via `deploy/deploy.sh`).
- Übernahme der lokalen SQLite-Daten auf den Server (Backlog; DB startet leer,
  Import via Web-Upload möglich).
- `GITHUB_TOKEN`/Bugreport und `/api/settings`-Persistenz im Container (Backlog).
- Multi-User/echtes Login — Single-User-Token bleibt.

## Testplan

- pytest: Cookie-Modus gated Seiten/Statics/API, `?token=` setzt Cookie +
  Redirect, falscher Token 401, Desktop-Modus unverändert, WS akzeptiert Cookie,
  Upload-Basename-Fix.
- Lokal: `docker compose -f docker-compose.prod.yml up` + Smoke (Seite, Auth, WS).
- Prod: CloudFront-URL im Browser, Login per Token-Link, Chat-Roundtrip.

## Betrieb (Runbook)

- **Erstes Deployment:** `deploy/provision-aws.sh`, dann
  `aws cloudfront wait distribution-deployed --id <dist-id> --profile drinkwise`,
  dann den ausgegebenen Login-Link öffnen.
- **Redeploy:** `export CTF_INSTANCE_ID=<id>` und `deploy/deploy.sh`
  (holt origin/main, refresh-env, compose up -d --build).
- **Logs:** `aws ssm start-session --target <instance-id> --profile drinkwise`,
  dann `docker logs -f ctf-web`.
- **Secrets ändern:** SSM-Parameter unter `/ctf/prod/` ändern, dann Redeploy.
- Ressourcen-IDs/URL: siehe Abschnitt „Live-Ressourcen" (wird nach dem Anlegen ergänzt).
