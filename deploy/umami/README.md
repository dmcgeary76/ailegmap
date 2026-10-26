# Umami on the VPS

Visit analytics for the map, self-hosted next to it. Cookieless; no personal data; no consent banner.

```bash
# on the VPS
mkdir -p /docker/umami
cp /docker/ailegmap/deploy/umami/docker-compose.yml /docker/ailegmap/deploy/umami/.env.example /docker/umami/
cd /docker/umami && cp .env.example .env
openssl rand -hex 32      # -> APP_SECRET in .env
openssl rand -hex 32      # -> POSTGRES_PASSWORD in .env
docker compose up -d
docker compose logs -f umami     # wait for "ready" on port 3000
```

Before that, add a DNS A record: `analytics.edtecharchitect.com` -> the VPS, so Traefik can get a certificate.

Then in the browser at https://analytics.edtecharchitect.com:

1. Log in as `admin` / `umami` and change the password immediately (Settings -> Profile).
2. Settings -> Websites -> Add website: name "K-12 AI Legislative Map", domain `map.edtecharchitect.com`.
3. Copy the website id into `frontend/.env.production` in the repo (see the top-level README, "Visit analytics"), commit, push. Pages and the VPS refresh pick it up on their next build.

Both the Pages copy and the VPS copy report to the same site; filter by hostname in Umami to tell them apart.

Upgrades: `docker compose pull && docker compose up -d`. Data lives in the `umami-db` volume.
