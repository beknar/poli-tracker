#!/usr/bin/env bash
# Serve poli-tracker over HTTPS with a SELF-SIGNED certificate.
#
#   nginx (443, TLS, self-signed)  ->  gunicorn (127.0.0.1:8000)
#
# Self-signed means NO Let's Encrypt, so there is no DNS/HTTP-01 dependency — fine
# for a service that isn't always online and whose DNS is managed by hand.
# Browsers will show a "not secure / unknown issuer" warning that you accept once.
#
# PREREQUISITES:
#   1. The app is installed at /opt/poli-tracker with its virtualenv.
#   2. Inbound TCP 443 is open (cloud firewall/security group + host); 80 too if
#      you want the HTTP->HTTPS redirect.
#   (No DNS record is required for the cert; the name is just baked into it so it
#    matches when you do point poli-tracker.rpg4you.com at the box by hand.)
#
# Usage:  sudo ./setup-https.sh [DOMAIN]
set -euxo pipefail

DOMAIN="${1:-poli-tracker.rpg4you.com}"
CRT=/etc/ssl/certs/poli-tracker-selfsigned.crt
KEY=/etc/ssl/private/poli-tracker-selfsigned.key

# 1. Install nginx (+ openssl, usually already present).
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y nginx openssl

# 2. Point gunicorn at localhost:8000 (production unit), then (re)start it.
install -m 0644 /opt/poli-tracker/deploy/poli-tracker.service \
  /etc/systemd/system/poli-tracker.service
systemctl daemon-reload
systemctl enable --now poli-tracker

# 3. Generate a self-signed cert (valid ~10 years) with the domain as CN + SAN.
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$KEY" -out "$CRT" -days 3650 \
  -subj "/CN=${DOMAIN}" -addext "subjectAltName=DNS:${DOMAIN}"
chmod 600 "$KEY"

# 4. nginx: redirect 80 -> 443, serve TLS on 443, proxy to gunicorn.
cat >/etc/nginx/sites-available/poli-tracker <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}
server {
    listen 443 ssl;
    server_name ${DOMAIN};

    ssl_certificate     ${CRT};
    ssl_certificate_key ${KEY};

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

echo "Done. Visit: https://${DOMAIN}  (accept the self-signed certificate warning)"
