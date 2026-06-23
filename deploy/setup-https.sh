#!/usr/bin/env bash
# Serve poli-tracker over HTTPS with a real Let's Encrypt certificate.
#
#   nginx (443, TLS)  ->  gunicorn (127.0.0.1:8000)
#
# PREREQUISITES (must be true BEFORE running this):
#   1. The app is installed at /opt/poli-tracker and the poli-tracker systemd
#      service runs gunicorn on 127.0.0.1:8000 (use deploy/poli-tracker.service).
#   2. The DNS name resolves to THIS server's public IP:
#         poli-tracker.rpg4you.com  A  <this server's public IP>
#   3. Inbound TCP 80 AND 443 are open (cloud firewall/security group + host).
#
# Usage:  sudo ./setup-https.sh [DOMAIN] [EMAIL]
set -euxo pipefail

DOMAIN="${1:-poli-tracker.rpg4you.com}"
EMAIL="${2:-admin@rpg4you.com}"

# 1. Install nginx + certbot (Ubuntu/Debian).
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y nginx certbot python3-certbot-nginx

# 2. Point gunicorn at localhost:8000 (production unit), then (re)start it.
install -m 0644 /opt/poli-tracker/deploy/poli-tracker.service \
  /etc/systemd/system/poli-tracker.service
systemctl daemon-reload
systemctl enable --now poli-tracker

# 3. nginx reverse proxy (HTTP for now; certbot adds the TLS/redirect in step 4).
cat >/etc/nginx/sites-available/poli-tracker <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/poli-tracker /etc/nginx/sites-enabled/poli-tracker
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# 4. Obtain + install the Let's Encrypt cert, and add the HTTP->HTTPS redirect.
#    certbot edits the nginx config in place and sets up auto-renewal (systemd timer).
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${EMAIL}" --redirect
systemctl reload nginx

echo "Done. Visit: https://${DOMAIN}"
