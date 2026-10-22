# Production deployment

Fibonacci runs its Next.js app on Vercel and its API, Celery worker, Redis, Nginx, and Certbot on a Docker host. Use a supported Linux server with Docker Engine and the Docker Compose plugin. Configure DNS so `api.wizetale.com` resolves to that server. Vercel manages DNS and TLS for the website domains.

## 1. Configure the API server

1. Check out the `main` branch in `REMOTE_PROJECT_DIR` on the API host. Create the deployment user with SSH access and Docker permission; do not deploy as root.
2. Copy the repository-root `.env.example` to `.env` and set the real values for Supabase, media storage, Gemini, the selected image provider (`IMAGE_PROVIDER=cloudflare` requires `CLOUDFLARE_ACCOUNT_ID` and a Workers AI token), and any selected speech provider. Keep `.env` readable only by the deployment account (`chmod 600 .env`).
3. Confirm the Supabase schema and private storage bucket are installed as described in [`../supabase/README.md`](../supabase/README.md).
4. Set `GEMINI_BILLING_TIER=paid` only after verifying the project has the paid data tier required by production generation. The API refuses startup when the value is `unknown`.
5. Verify that DNS for `api.wizetale.com` already points to this host and that inbound ports 80 and 443 are open.

The API and Celery containers read the repository-root `.env`. Redis and the API are reachable only on the private Docker network. Only Nginx publishes ports 80 and 443.

## 2. Obtain the first TLS certificate

The normal Nginx config requires a certificate, so bootstrap it with the HTTP-only config first:

```sh
docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml up -d redis api celery-worker nginx certbot

docker compose -f docker-compose.yml -f docker-compose.bootstrap.yml run --rm --entrypoint certbot certbot \
  certonly --webroot -w /var/www/certbot -d api.wizetale.com \
  --email "$LETSENCRYPT_EMAIL" --agree-tos --non-interactive

docker compose up -d --force-recreate nginx certbot
```

Set `LETSENCRYPT_EMAIL` in the deployment shell before the Certbot command. Once issued, the certificate is stored under `data/certbot/conf`; keep that directory backed up and private. The normal Certbot service renews it, and Nginx reloads periodically to use renewed certificates.

## 3. Configure Vercel

Create a Vercel project with `wizetale-app` as its Root Directory and use the checked-in lockfile (`npm ci`). Add the production environment variables:

- `NEXT_PUBLIC_SUPABASE_URL`: the Supabase project URL.
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`: the Supabase publishable key. This key is designed for browser use; database access still depends on RLS.
- `BACKEND_API_URL=https://api.wizetale.com`: server-only. Do not prefix it with `NEXT_PUBLIC_`.
- Optional Firebase Analytics public keys only if that integration is still enabled.

Do not place `SUPABASE_SERVICE_ROLE_KEY`, R2 credentials, Gemini credentials, or Redis credentials in Vercel or any `NEXT_PUBLIC_` variable. Add `wizetale.com` and `www.wizetale.com` as Vercel domains, then set the DNS records Vercel provides.

## 4. Deploy API updates

From a trusted checkout, set `DEPLOY_HOST`, `DEPLOY_USER`, and `REMOTE_PROJECT_DIR`, then run `./deploy.sh`. The script fast-forwards the remote `main` branch, builds the API and worker, starts the stack, and checks `https://api.wizetale.com/health`. It refuses missing settings and does not reset the remote working tree.

For the first deployment, issue the certificate before running `deploy.sh`. For later deploys, the script assumes the host already has a valid TLS certificate and the remote checkout is on `main`.

## 5. Verify live services

- `https://api.wizetale.com/health` returns `{"status":"ok"}`.
- `https://wizetale.com` and `https://www.wizetale.com` load over HTTPS.
- Sign-up, email confirmation, sign-in, draft creation, rendering, media playback, quiz saving, and account deletion work in a production test account.
- Celery worker and API logs show healthy startup without credentials or user content.
- Verify provider billing, Redis persistence, database backups, media deletion, and alerting in the actual service dashboards.

The browser-facing app proxies API calls through Next.js. Do not use a raw API IP or an `http://` backend URL in production.
