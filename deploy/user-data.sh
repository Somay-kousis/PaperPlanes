#!/usr/bin/env bash
# EC2 user-data — machine prep for a PaperPlanes host (Ubuntu 22.04/24.04, t3.small).
#
# This runs ONCE at first boot as root. It only prepares the box (Docker + repo).
# It deliberately does NOT start the app: the app needs `.env.prod` (secrets that
# are never in git), which you create by hand over SSH. See docs/DEPLOY.md.
set -euxo pipefail

# --- Docker Engine + Compose plugin (official repo) ---
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
usermod -aG docker ubuntu

# --- App source ---
# Replace with your fork if different.
git clone https://github.com/Somay-kousis/PaperPlanes.git /opt/paperplanes || true
chown -R ubuntu:ubuntu /opt/paperplanes

cat > /etc/motd <<'EOF'
==================================================================
 PaperPlanes host is prepared. To bring the app up:
   cd /opt/paperplanes
   cp deploy/.env.prod.example .env.prod && nano .env.prod   # fill secrets
   # apply the prod schema (CockroachDB Cloud):
   docker compose --env-file .env.prod --project-directory . \
     -f deploy/docker-compose.prod.yml run --rm backend python -m app.scripts.init_db
   # start it:
   docker compose --env-file .env.prod --project-directory . \
     -f deploy/docker-compose.prod.yml up -d --build
 Full runbook: docs/DEPLOY.md
==================================================================
EOF
