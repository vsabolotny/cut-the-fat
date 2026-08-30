#!/bin/bash
# Spült alle SSM-Parameter unter /ctf/prod/ nach /opt/ctf/.env (atomisch).
# Läuft auf der EC2-Instanz (Instance-Role liefert die Credentials).
set -euo pipefail

REGION="eu-central-1"
PARAM_PATH="/ctf/prod/"
ENV_FILE="/opt/ctf/.env"

aws ssm get-parameters-by-path \
  --path "$PARAM_PATH" \
  --with-decryption \
  --region "$REGION" \
  --query 'Parameters[].{Name:Name,Value:Value}' \
  --output json |
  jq -r --arg p "$PARAM_PATH" '.[] | (.Name | ltrimstr($p)) + "=" + .Value' \
  > "$ENV_FILE.new"

chmod 600 "$ENV_FILE.new"

# Fail closed: lieber die alte .env behalten als mit leerem Token starten —
# ohne CTF_AUTH_TOKEN wäre die App völlig ungeschützt erreichbar.
if ! grep -q '^CTF_AUTH_TOKEN=.\+' "$ENV_FILE.new"; then
  rm -f "$ENV_FILE.new"
  echo "FEHLER: CTF_AUTH_TOKEN fehlt in $PARAM_PATH — .env unverändert gelassen" >&2
  exit 1
fi

mv "$ENV_FILE.new" "$ENV_FILE"
echo "wrote $(wc -l < "$ENV_FILE") vars to $ENV_FILE"
