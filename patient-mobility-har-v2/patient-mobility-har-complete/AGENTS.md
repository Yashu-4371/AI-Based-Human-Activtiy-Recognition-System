# AGENTS.md — Context for AI Agents

This file provides context and conventions for AI coding agents working on this repository.

---

## Project Overview

**MobilityWatch** — an AI-based Human Activity Recognition (HAR) system for patient mobility assessment.

A camera-only, non-intrusive patient monitoring platform that:
- Classifies patient activities (walking, standing, sitting, lying) in real time from MediaPipe pose landmarks via a Random Forest classifier
- Detects falls using a two-stage rule engine (sudden-onset trigger + sustained-posture confirmation)
- Detects prolonged inactivity with configurable thresholds
- Alerts caregivers (in-app, email/SMTP, optional Telegram) with automatic screenshots
- Manages patients (CRUD, photos, medical notes, room/doctor/emergency contacts)
- Generates reports (PDF with charts + activity timeline, CSV, XLSX with native Excel charts) and analytics
- Streams live video over WebSocket with pose-skeleton overlay

This is an academic/portfolio reference implementation — **not** certified for clinical use.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2, JWT (python-jose), passlib/bcrypt |
| Computer vision | OpenCV, MediaPipe Pose |
| Machine learning | scikit-learn Random Forest, joblib |
| Database | SQLite (dev default), PostgreSQL-ready via `DATABASE_URL` |
| Frontend | React 18, Vite 5, TypeScript, TailwindCSS, ShadCN-style UI components, Recharts, Framer Motion, Axios |
| Reports | ReportLab (PDF), openpyxl (XLSX), matplotlib |
| Deployment | Docker, docker-compose, GitHub Actions CI |

## Repository Layout

```
patient-mobility-har/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entrypoint
│   │   ├── config.py            # pydantic-settings config
│   │   ├── api/                 # Routers: auth, patients, alerts, activities,
│   │   │                        #   analytics, reports, camera, settings, websocket
│   │   ├── models/              # SQLAlchemy models (user, patient, activity, alert,
│   │   │                        #   report, log, camera_setting, system_setting)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic (auth, patient, alert, activity,
│   │   │                        #   analytics, report services)
│   │   ├── ml/                  # ML pipeline: pose_estimator, feature_extractor,
│   │   │                        #   activity_classifier, fall_detector,
│   │   │                        #   inactivity_detector, train_model,
│   │   │                        #   data/generate_synthetic_data.py
│   │   ├── pipeline/            # monitoring_worker (per-camera processing loop)
│   │   ├── camera/              # camera_manager, frame_buffer
│   │   ├── alerts/              # email_notifier (SMTP), telegram_notifier, alarm_sound
│   │   │                        #   (caregiver recipient lookup: services/alert_email_service.py)
│   │   ├── database/            # session, init_db
│   │   └── utils/               # security, logger, file_storage
│   ├── models_store/            # Trained model artifacts (activity_rf.pkl, activity_scaler.pkl)
│   ├── tests/                   # pytest suite (conftest + auth, patients, activities,
│   │                            #   alerts, fall_detector, feature_extractor tests)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # Dashboard, LiveMonitor, Patients, PatientDetail,
│   │   │                        #   Alerts, Analytics, Reports, Caregivers, Login
│   │   ├── components/          # ui/ (shadcn-style), dashboard/, patients/,
│   │   │                        #   camera/, layout/
│   │   ├── services/            # API clients: api.ts (axios base), auth, patient,
│   │   │                        #   alert, analytics, report, camera services
│   │   ├── hooks/               # useAuth, usePatients, useWebSocket
│   │   ├── context/             # AuthContext
│   │   ├── layouts/             # DashboardLayout
│   │   └── lib/                 # utils (cn helper for class merging)
│   ├── package.json
│   └── Dockerfile               # Builds to nginx-served static app
├── docs/                        # architecture.md, folder_structure.md,
│                                #   installation_guide.md, deployment_guide.md
├── .github/workflows/ci.yml     # CI pipeline
├── docker-compose.yml           # backend (:8000) + frontend (:80)
└── .env.example                 # Root env template for docker-compose
```

## Commands

### Backend (from `backend/`)

```bash
# Setup
python -m venv venv
venv\Scripts\activate            # Windows (use source venv/bin/activate on Unix)
pip install -r requirements.txt

# Train the ML model (REQUIRED before first run — ships untrained;
# creates models_store/activity_rf.pkl and activity_scaler.pkl)
python -m app.ml.train_model

# Run dev server
uvicorn app.main:app --reload    # http://localhost:8000, Swagger at /docs

# Tests
pytest -v

# Lint/typecheck: no dedicated commands configured yet.
# If adding one, update this section.
```

### Frontend (from `frontend/`)

```bash
npm install

# Dev server
npm run dev                      # Vite dev server

# Type check + production build (tsc -b && vite build)
npm run build

# Lint
npm run lint                     # eslint . --ext ts,tsx
```

Verification expectations:
- Backend changes → run `pytest -v` before finishing.
- Frontend changes → run `npm run lint` and `npm run build` before finishing.

### Docker (from repo root)

```bash
cp .env.example .env             # MUST set SECRET_KEY and DEFAULT_ADMIN_PASSWORD
docker-compose up --build
```

- Frontend: http://localhost (nginx on port 80)
- Backend API + Swagger: http://localhost:8000/docs
- Health endpoint used by compose healthcheck: `/api/v1/health`

## Environment & Configuration

- Root `.env.example` feeds **docker-compose variable substitution only**.
- For running services individually, use `backend/.env.example` and `frontend/.env.example`.
- Key variables: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
  `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD`, `FRONTEND_ORIGIN`,
  sender-only SMTP settings (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`;
  caregiver recipients come from the database, see docs/email_alerts.md), Telegram settings (`TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`).
- Never commit real secrets or `.env` files.

## Architecture Notes

- **API prefix**: all routes are mounted under `/api/v1` (health: `/api/v1/health`).
- **Auth**: JWT bearer tokens; two roles — `admin` and `caregiver`. Role-based permission
  checks live in `app/api/deps.py`; enforce them via dependencies, not ad-hoc checks.
- **Layering convention**: API routers (`app/api/`) stay thin; business logic goes in
  `app/services/`; DB access through SQLAlchemy session from `app/database/session.py`;
  request/response shapes in `app/schemas/`. Follow this when adding endpoints.
- **ML pipeline**: camera frames → `camera/camera_manager.py` + `frame_buffer.py` →
  `pipeline/monitoring_worker.py` → `ml/pose_estimator.py` (MediaPipe landmarks) →
  `ml/feature_extractor.py` → `ml/activity_classifier.py` (Random Forest) plus rule-based
  `ml/fall_detector.py` (two-stage: trigger then sustained-posture confirmation) and
  `ml/inactivity_detector.py` → alerts via `alerts/*` notifiers + WebSocket broadcast.
- **Fall detection tuning**: the two-stage design intentionally avoids false alarms from
  quick bends/sits. Do not simplify it to single-frame detection without discussion.
- **Inactivity detection**: "lying still" is often expected behavior (e.g., sleeping),
  not automatically a warning. Thresholds are configurable via settings.
- **Model artifacts**: `.pkl` files under `backend/models_store/` are generated by
  training, not hand-edited. Real training needs recorded/public multi-subject data (docs/activity_recognition.md); `--synthetic` is a placeholder only
  (`app/ml/data/generate_synthetic_data.py`) — see docs/installation_guide.md for
  substituting real recorded data.
- **WebSocket**: live video + skeleton overlays stream through `app/api/websocket.py`;
  frontend consumes it via `src/hooks/useWebSocket.ts`.
- **Reports**: PDF via ReportLab with matplotlib-rendered chart images; XLSX via openpyxl
  with native editable charts. Logic in `app/services/report_service.py` +
  `report_charts.py`.
- **Camera sources**: webcam/USB/IP/RTSP supported, with reconnect-with-backoff on failure
  (see `camera_manager.py`). Physical webcam passthrough into Linux containers requires
  `--device=/dev/video0`.

## Conventions

- Backend: Python type hints everywhere; Pydantic v2 style schemas; SQLAlchemy 2.0 style.
  Use the existing logger from `app/utils/logger.py`, not bare prints.
- Frontend: TypeScript strict; functional components + hooks; shadcn-style primitives in
  `components/ui/` built on Radix; class merging via `cn()` from `lib/utils.ts`
  (clsx + tailwind-merge); icons from lucide-react; charts via Recharts; animations via
  framer-motion. Keep styling Tailwind-first.
- API client calls belong in `frontend/src/services/*` — don't call axios directly from
  components.
- New routes/pages must be wired into routing in `App.tsx` and protected via
  `ProtectedRoute` where appropriate.
- Docs in `docs/` are part of the deliverable — update relevant guides when changing
  setup, deployment, or architecture.

## Gotchas

- `venv/`, `node_modules/`, `__pycache__/`, logs, and `patient_mobility.db` exist locally
  but are gitignored — don't commit them.
- On Windows, OpenCV/MediaPipe need the venv activated in each shell session.
- The backend creates the admin user and initializes the DB on startup
  (`app/database/init_db.py`) using the `DEFAULT_ADMIN_*` env vars.
- CORS origin comes from `FRONTEND_ORIGIN` — keep frontend/backend origins consistent
  across configs.
