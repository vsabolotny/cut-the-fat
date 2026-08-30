#!/bin/bash
# EC2 User-Data (AL2023): einmaliges Bootstrap der Web-App-Instanz (CAT-27).
set -euxo pipefail

dnf install -y docker git jq
systemctl enable --now docker

# docker compose v2 Plugin (nicht in den AL2023-Repos)
COMPOSE_VERSION="v2.29.7"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL \
  "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

git clone https://github.com/vsabolotny/cut-the-fat.git /opt/ctf

/opt/ctf/deploy/refresh-env.sh

cd /opt/ctf
docker compose -f docker-compose.prod.yml up -d --build
