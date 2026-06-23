# Deploying poli-tracker over HTTPS (self-signed)

Serve the app over HTTPS using a **self-signed certificate** and nginx as a TLS
reverse proxy in front of gunicorn:

```
client ──HTTPS:443──► nginx (self-signed TLS) ──HTTP──► gunicorn 127.0.0.1:8000 ──► Flask app
```

Self-signed is intentional here: the service isn't online all the time and the
DNS for `poli-tracker.rpg4you.com` is managed by hand, so there's no value in
Let's Encrypt (which would need the domain to resolve and port 80 reachable for
its challenge). The trade-off: browsers show a **"not secure / unknown issuer"**
warning that you click through once.

## Prerequisites

1. **App installed** at `/opt/poli-tracker` with its virtualenv
   (`/opt/poli-tracker/.venv`).
2. **Firewall** — inbound TCP **443** open (cloud security group / VPC firewall +
   host); also **80** if you want the HTTP→HTTPS redirect.
3. **No DNS record is required** for the certificate. To reach the app *by name*
   you'll still point `poli-tracker.rpg4you.com` at the server (by hand, or via
   `/etc/hosts`); the cert bakes that name in as CN + SAN so it matches. You can
   also just hit `https://<server-ip>` (with the same cert warning).

## One-time setup

```bash
cd /opt/poli-tracker
sudo deploy/setup-https.sh poli-tracker.rpg4you.com
```

`setup-https.sh`:
1. installs `nginx` (+ `openssl`);
2. installs `deploy/poli-tracker.service` (gunicorn on **127.0.0.1:8000**) and
   starts it;
3. generates a **self-signed** cert (~10-year validity) for the domain;
4. configures nginx to serve TLS on 443, proxy to gunicorn, and redirect 80→443.

Then browse to **https://poli-tracker.rpg4you.com** and accept the certificate
warning.

## Notes

- The cert lasts ~10 years (no renewal step). Re-run the script to regenerate.
- gunicorn binds **localhost only**; nginx owns 80/443. This differs from the
  throwaway multi-cloud demo (`terraform/app-multi-cloud` in the devops repo),
  which runs gunicorn directly on `:80` over plain HTTP.
- To trust the cert without the browser warning, import the generated
  `/etc/ssl/certs/poli-tracker-selfsigned.crt` into your client's trust store
  (optional).
