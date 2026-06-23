# Deploying poli-tracker over HTTPS

Serve the app at **https://poli-tracker.rpg4you.com** with a real Let's Encrypt
certificate, using nginx as a TLS reverse proxy in front of gunicorn:

```
client ──HTTPS:443──► nginx ──HTTP──► gunicorn 127.0.0.1:8000 ──► Flask app
```

## Prerequisites

1. **App installed** at `/opt/poli-tracker` with its virtualenv
   (`/opt/poli-tracker/.venv`) — e.g. cloned + `pip install -r requirements.txt`.
2. **DNS** — create an `A` record so the domain resolves to the server's public IP:
   ```
   poli-tracker.rpg4you.com.  A  <server public IP>
   ```
   (Let's Encrypt's HTTP-01 challenge verifies you control the domain by reaching
   it on port 80, so this must be in place first.)
3. **Firewall** — inbound TCP **80 and 443** open at both the cloud layer
   (security group / VPC firewall) and the host firewall.

## One-time setup

```bash
cd /opt/poli-tracker
sudo deploy/setup-https.sh poli-tracker.rpg4you.com you@rpg4you.com
```

`setup-https.sh`:
1. installs `nginx`, `certbot`, `python3-certbot-nginx`;
2. installs `deploy/poli-tracker.service` (gunicorn bound to **127.0.0.1:8000**)
   and starts it;
3. configures nginx as a reverse proxy for the domain;
4. runs `certbot --nginx` to obtain + install the cert, add the HTTP→HTTPS
   redirect, and register **automatic renewal** (certbot's systemd timer).

Then browse to **https://poli-tracker.rpg4you.com**.

## Notes

- The certificate **auto-renews** (certbot installs a `systemd` timer); renewal
  needs port 80 to stay reachable.
- gunicorn binds **localhost only** here (nginx owns 80/443). This differs from
  the throwaway multi-cloud demo (`terraform/app-multi-cloud` in the devops repo),
  which runs gunicorn directly on `:80` over plain HTTP — that's fine for the
  ephemeral demo, but use this HTTPS setup for a real, named deployment.
- To change the domain, pass it as the first argument to `setup-https.sh`.
