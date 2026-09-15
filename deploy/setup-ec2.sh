#!/usr/bin/env bash
# One-time provisioning for a fresh Ubuntu 22.04/24.04 EC2 instance.
# Run as: ssh onto the instance, then `sudo bash setup-ec2.sh`.
# See deploy/DEPLOY.md for the steps before and after this script.
set -euo pipefail

apt-get update
apt-get install -y ca-certificates curl gnupg nginx certbot python3-certbot-nginx git

# --- Docker Engine + Compose plugin (official repo, not the Ubuntu apt one,
# which lags and sometimes ships without the compose plugin) ---
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

usermod -aG docker "${SUDO_USER:-ubuntu}"

# /opt/spacio is expected to already exist (see deploy/DEPLOY.md — it has
# to be chowned before `git clone` can write into it, which has to happen
# before this script, which lives inside the repo, can even be run). The
# mkdir here is just defensive idempotency; /var/www/spacio is the one this
# script is actually responsible for creating.
mkdir -p /opt/spacio /var/www/spacio
chown -R "${SUDO_USER:-ubuntu}:${SUDO_USER:-ubuntu}" /opt/spacio /var/www/spacio

echo
echo "Done. Log out and back in (or 'newgrp docker') so the docker group applies."
echo "Next: clone the repo into /opt/spacio, add api/.env.production, then see deploy/DEPLOY.md."
