# Running Fibonacci locally

You need **Docker** (with Docker Compose) and **Node.js 20 or newer**.

## 1. Add the secret files

The secret files are not in this zip. Get them from the project owner and put them here:

| File | Where it goes |
| --- | --- |
| `.env` | the project root, next to `docker-compose.yml` |
| `wizetale-app/.env.local` | inside the `wizetale-app` folder |

If you're setting it up yourself instead, copy `.env.example` to `.env` and `wizetale-app/.env.example` to `wizetale-app/.env.local`, then fill in your own keys. The root `.env` also needs this line (any random password works):

```
TALESPARK_LOCAL_REDIS_PASSWORD=change-me-to-something-random
```

In `wizetale-app/.env.local`, set `BACKEND_API_URL=http://localhost:8001`.

## 2. Start the backend (API, worker, Redis)

From the project root:

```
docker compose -p talespark-local -f docker-compose.yml -f docker-compose.local.yml up -d --build redis api celery-worker
```

The first build takes a few minutes. When it's done, open http://localhost:8001/health. It should show `{"status":"ok"}`.

## 3. Start the website

```
cd wizetale-app
npm ci
npm run dev
```

Open **http://localhost:3001**, create an account, and try it.

## Notes

- Generating a story or quiz can take up to about a minute when the AI provider is busy. Wait for it to finish rather than clicking again.
- Teacher features (lessons, uploading sources) need **Teacher mode**, which you can switch on from the header.
- To stop the backend: `docker compose -p talespark-local -f docker-compose.yml -f docker-compose.local.yml down`
