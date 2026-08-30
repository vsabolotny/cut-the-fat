#!/bin/bash
# Redeploy der Web-App auf die EC2-Instanz — per SSM, ohne SSH.
# Lokal ausführen: deploy/deploy.sh   (braucht aws-Profil "drinkwise")
set -euo pipefail

PROFILE="${AWS_PROFILE_OVERRIDE:-drinkwise}"
REGION="eu-central-1"
INSTANCE_ID="${CTF_INSTANCE_ID:?CTF_INSTANCE_ID setzen (siehe doc/CAT-27-AWS-DEPLOYMENT.md)}"

CMD_ID=$(aws ssm send-command \
  --profile "$PROFILE" --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "ctf-web redeploy" \
  --parameters 'commands=[
    "set -euo pipefail",
    "cd /opt/ctf",
    "git fetch --all --prune",
    "git reset --hard origin/main",
    "deploy/refresh-env.sh",
    "docker compose -f docker-compose.prod.yml up -d --build",
    "sleep 10",
    "curl -fsS http://127.0.0.1/health",
    "docker image prune -f"
  ]' \
  --query 'Command.CommandId' --output text)

echo "SSM command: $CMD_ID — polling…"
for _ in $(seq 1 60); do
  STATUS=$(aws ssm get-command-invocation \
    --profile "$PROFILE" --region "$REGION" \
    --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" \
    --query 'Status' --output text 2>/dev/null || echo Pending)
  case "$STATUS" in
    Success|Failed|Cancelled|TimedOut) break ;;
    *) sleep 5 ;;
  esac
done

aws ssm get-command-invocation \
  --profile "$PROFILE" --region "$REGION" \
  --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Stdout:StandardOutputContent,Stderr:StandardErrorContent}' \
  --output json

[ "$STATUS" = "Success" ]
