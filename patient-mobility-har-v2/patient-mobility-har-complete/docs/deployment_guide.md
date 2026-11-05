# Deployment Guide

This guide covers deploying the system with Docker (recommended) and the production considerations that go beyond local development.

## 1. Docker deployment

### One-command start
```bash
cp .env.example .env      # edit values — see below
docker-compose up --build
```
This builds and starts two containers:
- `har-backend` — FastAPI + Uvicorn on port `8000`
- `har-frontend` — the Vite production build served via Nginx on port `80`, which proxies `/api`, `/uploads`, and `/ws` to the backend container (see `frontend/nginx.conf`)

### Required `.env` values
`docker-compose.yml` will refuse to start if these aren't set (no insecure defaults are baked in):
- `SECRET_KEY` — generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `DEFAULT_ADMIN_PASSWORD` — the seeded admin account's password

Everything else (SMTP, Telegram, frontend origin) has a safe default or no-ops if left blank.

### Camera passthrough
This is the most common deployment gotcha. A **physical webcam plugged into the host** needs an explicit device mapping to be visible inside the backend container:

```yaml
# in docker-compose.yml, under the backend service
devices:
  - /dev/video0:/dev/video0
```
This only works on **Linux hosts** — Docker Desktop on macOS/Windows cannot pass through USB devices to containers at all. On those platforms, either:
- Run the backend natively (see [installation_guide.md](installation_guide.md)) and only containerize the frontend, or
- Use an **IP or RTSP camera** instead of a USB webcam — network camera sources work identically whether the backend is containerized or not, since they're accessed over the network rather than a device file.

### Volumes
Three named volumes persist data across container restarts/rebuilds:
- `backend_uploads` — patient photos, alert screenshots, generated reports
- `backend_models` — the trained `.pkl` model files
- `backend_logs` — application logs

**Important:** the trained model is not baked into the image. After first deploy, exec into the backend container once to train it:
```bash
docker-compose exec backend python -m app.ml.train_model
```

## 2. Switching to PostgreSQL

SQLite (the default) is fine for a single-instance deployment or demo. For production with concurrent writers, switch to Postgres:

1. Uncomment the `db` service and `postgres_data` volume in `docker-compose.yml`
2. Set `POSTGRES_PASSWORD` (and optionally `POSTGRES_DB`/`POSTGRES_USER`) in `.env`
3. Change `DATABASE_URL` in `.env` to:
   ```
   DATABASE_URL=postgresql://har_user:<password>@db:5432/patient_mobility
   ```
No application code changes are needed — every model is written against SQLAlchemy's engine-agnostic API (see `docs/architecture.md` for why this was a deliberate design choice from the start).

## 3. HTTPS / TLS

Neither Nginx config nor Uvicorn in this repo terminates TLS — that's expected to be handled by whatever sits in front of this stack in production (a reverse proxy like Traefik/Caddy, or a cloud load balancer). Do not expose port `8000` or `80` directly to the public internet without a TLS-terminating layer in front, especially since this system handles authentication tokens and real patient data.

## 4. Scaling and reliability notes

- The monitoring pipeline (`app/pipeline/monitoring_worker.py`) runs as a single in-process background thread — the current architecture supports **one active camera session per backend process**. Running multiple simultaneous camera feeds requires either multiple backend instances (one per camera) behind a router, or extending the worker to manage multiple concurrent threads — this is flagged as a scaling boundary, not silently glossed over.
- The WebSocket live-feed endpoint pushes to every connected client independently; many simultaneous dashboard viewers is fine, but many simultaneous *camera sources* is the actual scaling constraint above.
- Activity data is written per-segment (not per-frame) specifically to keep the database small at scale — see the architecture doc's rationale.

## 5. Regulatory / data-sensitivity note

This system processes video and inferred activity data about real people, in a healthcare context. Before any real clinical deployment (as opposed to an academic/demo setting), this needs a real compliance review — HIPAA (US), GDPR (EU), or the equivalent in your jurisdiction — covering at minimum: data retention policy for video/screenshots, access-control audit logging (the `logs` table here is a starting point, not a complete audit trail), encryption at rest for the uploads volume, and a documented consent process for the patients being monitored. Nothing in this codebase should be treated as compliance guidance — that determination has to come from someone qualified to make it for your specific deployment.

## 6. CI/CD

`.github/workflows/ci.yml` runs on every push/PR to `main`/`develop`:
1. Backend: installs dependencies, trains the model, runs `pytest`
2. Frontend: lints and builds
3. Docker: builds both images to catch Dockerfile regressions early

This validates the code builds and tests pass — it does not automatically deploy anywhere. Wire a deploy step (e.g. push images to a registry, trigger a redeploy on your hosting platform) onto the end of this workflow once you've chosen where this will actually run.
