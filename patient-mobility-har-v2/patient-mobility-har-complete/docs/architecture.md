# AI-Based Human Activity Recognition System for Patient Mobility Assessment
## Complete Software Architecture — Step 1

---

## 1. Folder Structure

```
patient-mobility-har/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app entrypoint, router registration, startup/shutdown events
│   │   ├── config.py                   # Settings loaded from .env (Pydantic BaseSettings)
│   │   ├── api/
│   │   │   ├── deps.py                 # Shared FastAPI dependencies (get_db, get_current_user, role guards)
│   │   │   ├── auth.py                 # /auth routes
│   │   │   ├── patients.py             # /patients routes
│   │   │   ├── activities.py           # /activities routes
│   │   │   ├── alerts.py               # /alerts routes
│   │   │   ├── reports.py              # /reports routes
│   │   │   ├── analytics.py            # /analytics routes
│   │   │   ├── camera.py               # /camera routes
│   │   │   ├── settings.py             # /settings routes
│   │   │   └── websocket.py            # /ws/live real-time channel
│   │   ├── models/                     # SQLAlchemy ORM models (one file per table)
│   │   │   ├── user.py
│   │   │   ├── patient.py
│   │   │   ├── activity.py
│   │   │   ├── alert.py
│   │   │   ├── report.py
│   │   │   ├── camera_setting.py
│   │   │   ├── system_setting.py
│   │   │   └── log.py
│   │   ├── schemas/                    # Pydantic request/response schemas (mirrors models/)
│   │   │   ├── user.py
│   │   │   ├── patient.py
│   │   │   ├── activity.py
│   │   │   ├── alert.py
│   │   │   ├── report.py
│   │   │   └── token.py
│   │   ├── database/
│   │   │   ├── session.py              # Engine + SessionLocal + Base
│   │   │   └── init_db.py              # Table creation, seed admin user
│   │   ├── services/                   # Business logic, decoupled from HTTP layer
│   │   │   ├── auth_service.py         # Password hashing, JWT issue/verify
│   │   │   ├── patient_service.py
│   │   │   ├── activity_service.py
│   │   │   ├── alert_service.py
│   │   │   ├── report_service.py       # PDF/CSV/Excel generation
│   │   │   └── analytics_service.py    # Aggregation queries for charts
│   │   ├── camera/
│   │   │   ├── camera_manager.py       # Opens/manages webcam, USB, IP, RTSP sources
│   │   │   └── frame_buffer.py         # Thread-safe latest-frame store for streaming
│   │   ├── ml/
│   │   │   ├── pose_estimator.py       # MediaPipe wrapper, landmark extraction
│   │   │   ├── feature_extractor.py    # Angles, distances, velocity, orientation
│   │   │   ├── activity_classifier.py  # Random Forest load/predict wrapper
│   │   │   ├── fall_detector.py        # Rule engine described in Step 1 doc
│   │   │   ├── inactivity_detector.py
│   │   │   ├── train_model.py          # Offline training script → saves .pkl
│   │   │   └── data/
│   │   │       ├── generate_synthetic_data.py
│   │   │       └── training_features.csv
│   │   ├── alerts/
│   │   │   ├── email_notifier.py
│   │   │   ├── telegram_notifier.py    # optional/bonus
│   │   │   └── alarm_sound.py
│   │   ├── pipeline/
│   │   │   └── monitoring_worker.py    # Orchestrates camera→pose→features→classify→fall→alert→DB→WS
│   │   └── utils/
│   │       ├── logger.py
│   │       ├── security.py
│   │       └── file_storage.py         # Screenshot/report file paths
│   ├── models_store/                   # Saved .pkl model artifacts (gitignored, regenerable)
│   ├── uploads/                        # Screenshots, patient photos, generated reports
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── LiveMonitor.tsx
│   │   │   ├── Patients.tsx
│   │   │   ├── PatientDetail.tsx
│   │   │   ├── Alerts.tsx
│   │   │   ├── Reports.tsx
│   │   │   ├── Analytics.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── ui/                     # ShadCN primitives (button, card, dialog, table…)
│   │   │   ├── dashboard/              # StatCard, ActivityChart, AlertFeed…
│   │   │   ├── camera/                 # LiveFeed, SkeletonOverlay, ActivityBadge
│   │   │   ├── patients/               # PatientCard, PatientForm
│   │   │   └── layout/                 # Sidebar, Topbar, ProtectedRoute
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useWebSocket.ts
│   │   │   └── usePatients.ts
│   │   ├── services/
│   │   │   ├── api.ts                  # Axios instance + interceptors (JWT attach/refresh)
│   │   │   ├── authService.ts
│   │   │   ├── patientService.ts
│   │   │   ├── alertService.ts
│   │   │   └── reportService.ts
│   │   ├── context/
│   │   │   └── AuthContext.tsx
│   │   ├── layouts/
│   │   │   └── DashboardLayout.tsx
│   │   └── assets/
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   └── Dockerfile
│
├── docker-compose.yml
├── README.md
└── docs/
    ├── architecture.md                 # this document
    └── api_documentation.md
```

**Design principle:** backend is layered strictly as `api → services → models/ml/camera`. Routes never touch the database or the ML pipeline directly — they call a service function. This means the ML pipeline can be tested and reused (e.g., in the training script) without ever booting FastAPI.

---

## 2. Backend Architecture

**Framework:** FastAPI, chosen for async support (needed for the WebSocket live feed and non-blocking camera I/O), automatic OpenAPI/Swagger docs, and Pydantic-native validation.

**Layers:**
1. **API layer** (`api/`) — thin. Parses requests, calls a service, returns a schema. No business logic.
2. **Service layer** (`services/`) — all business rules: "can this user resolve an alert", "how is a weekly report aggregated", etc. Framework-agnostic — could be reused by a CLI or a background job.
3. **Data layer** (`models/` + `database/`) — SQLAlchemy ORM. Repository-style access is done via service functions rather than a separate repository class, since project scope doesn't need that extra indirection.
4. **Domain-specific engines** (`ml/`, `camera/`, `alerts/`, `pipeline/`) — the CV/ML/notification machinery, invoked by the monitoring worker, not by API routes directly (routes only *read* the latest state these engines produce, and can start/stop them).

**Concurrency model:** The monitoring pipeline (`pipeline/monitoring_worker.py`) runs as a background asyncio task (or a separate thread if a CV call is blocking) started at app startup or via a `/camera/start` endpoint. It writes results into a thread-safe in-memory state object and calls the alert/DB services when something noteworthy happens. The WebSocket route subscribes to that state and pushes updates to connected dashboards — this avoids the frontend having to poll.

**Error handling & logging:** A global FastAPI exception handler converts uncaught exceptions into structured JSON error responses. `utils/logger.py` configures a rotating file logger; every service function logs at entry/error level, and critical events (fall detected, camera disconnected) also get written to the `logs` DB table for audit purposes.

**Validation:** All request/response bodies go through Pydantic schemas in `schemas/`, kept separate from ORM models so internal fields (password hashes, etc.) never leak into API responses.

---

## 3. Frontend Architecture

**Stack:** React + Vite + TypeScript + TailwindCSS + ShadCN UI + Framer Motion + Recharts + Lucide icons.

**Structure principle:** Pages are thin containers; all reusable visual pieces live in `components/`, grouped by feature domain (dashboard, camera, patients) rather than by type, so a developer working on "Live Monitor" finds everything relevant in one folder.

**State & data flow:**
- **Auth state** — `AuthContext` holds the JWT, current user, and role; wraps the whole app.
- **Server state** — plain fetch/axios calls through `services/*Service.ts`, called from pages/hooks. Given project scope, a dedicated data-fetching library (React Query) is optional polish, not a hard requirement — noted as an easy upgrade path later.
- **Live state** — `useWebSocket` hook maintains a single WS connection to `/ws/live` and exposes the latest activity/alert payload to any component that needs it (LiveMonitor page, Dashboard cards, AlertFeed).

**Routing & guards:** `ProtectedRoute` wraps role-restricted pages (e.g., Settings is admin-only); unauthenticated users are redirected to `/login`.

**Design system:** Professional hospital theme — blue/white palette, glassmorphism cards, rounded corners, consistent spacing scale via Tailwind config, dark/light mode toggle stored in `localStorage`-equivalent context state (per the artifact rules, actual persisted settings live server-side in the `settings` table, not browser storage, since this is a real deployed app rather than a Claude artifact).

**Responsiveness:** Mobile-first Tailwind breakpoints; the sidebar collapses to a bottom nav or hamburger drawer on small screens; charts resize via Recharts' `ResponsiveContainer`.

---

## 4. Database Architecture

**Engine:** SQLite for development/demo (zero setup, file-based, perfect for a viva laptop demo); SQLAlchemy models are written engine-agnostic so switching `DATABASE_URL` to a Postgres connection string is the only change needed for production.

**Schema (entities and relationships):**

```
users (1) ────────────< alerts.resolved_by
patients (1) ──────< activities
patients (1) ──────< alerts
patients (1) ──────< reports
camera_settings (1) ──< activities   (which camera observed this activity)
```

| Table | Key columns | Notes |
|---|---|---|
| `users` | id, name, email (unique), password_hash, role, created_at | role ∈ {admin, caregiver} |
| `patients` | id, name, photo_path, age, gender, blood_group, disease, doctor, room_number, emergency_contact, medical_notes, created_at | |
| `activities` | id, patient_id (FK), camera_id (FK), activity_type, confidence, started_at, ended_at, duration_sec | one row per continuous activity segment, not per frame |
| `alerts` | id, patient_id (FK), type, priority, status, message, screenshot_path, created_at, resolved_at, resolved_by (FK→users) | type ∈ {fall, inactivity, abnormal}; priority ∈ {critical, warning, normal} |
| `reports` | id, patient_id (FK), report_type, file_path, generated_at | report_type ∈ {daily, weekly, monthly} |
| `camera_settings` | id, name, source_type, source_uri, resolution, is_active | source_type ∈ {webcam, ip, rtsp} |
| `system_settings` | id, key (unique), value | key-value store for thresholds, email config, alarm sound, theme default |
| `logs` | id, level, message, module, created_at | audit + debugging trail |

**Why per-segment activity rows instead of per-frame:** at 15–30 FPS, logging every frame would generate millions of rows per day and make reports/analytics slow. Instead the pipeline only writes a new `activities` row when the classified activity *changes*, closing the previous row's `ended_at`/`duration_sec`. This keeps the table small and makes "how long did the patient walk today" a simple `SUM(duration_sec)` query.

---

## 5. Machine Learning Pipeline

```
Landmarks (33 MediaPipe points, x/y/z/visibility)
        ↓
Feature Extraction:
  • Joint angles (elbow, knee, hip, shoulder)
  • Joint distances (normalized by torso length, so it's scale-invariant)
  • Body inclination (torso vector vs. vertical axis)
  • Movement velocity (centroid delta over rolling window)
  • Aspect ratio of bounding box
        ↓
Feature Vector (fixed-length, e.g., ~20 features)
        ↓
Random Forest Classifier (scikit-learn, trained offline, loaded via joblib at runtime)
        ↓
Predicted activity + confidence score (walking / standing / sitting / lying)
```

**Training script (`train_model.py`):** reads `training_features.csv` (generated by `generate_synthetic_data.py` — see below), splits train/test, trains `RandomForestClassifier`, evaluates accuracy/confusion matrix, saves the model + a `StandardScaler` (if needed) to `models_store/activity_rf.pkl`. This script is run once offline, not at every server startup.

**Synthetic data generation:** Since a real annotated pose-activity dataset isn't available for this project, `generate_synthetic_data.py` procedurally generates plausible joint-angle/velocity feature rows per activity class using known biomechanical ranges (e.g., standing → near-zero knee bend, near-zero velocity, torso angle ≈ 0°; walking → cyclic knee bend, non-zero velocity; lying → torso angle ≈ 90°, near-zero velocity; sitting → hip/knee angle ≈ 90°, near-zero velocity), with added Gaussian noise for realism. This is clearly documented in the code and report as a synthetic-data approach — a legitimate and common technique for a Phase-I/II academic project, and the pipeline is designed so swapping in real recorded/annotated data later requires no code changes, only a new CSV.

**Future-ready hook:** `activity_classifier.py` exposes a `predict(features) -> (label, confidence)` interface; an LSTM/CNN model (for sequence-aware classification) can be dropped in behind the same interface later without touching the rest of the pipeline — satisfying the report's stated future-enhancement direction.

---

## 6. Computer Vision Pipeline

```
Camera Source (webcam/USB/IP/RTSP)
        ↓  camera_manager.py opens cv2.VideoCapture
Frame Grab (loop, target 15–30 FPS)
        ↓
Preprocessing: resize, color convert (BGR→RGB for MediaPipe), optional denoise
        ↓
MediaPipe Pose (pose_estimator.py): returns 33 landmarks per detected person
        ↓
Feature Extraction (feature_extractor.py)
        ↓
Activity Classification (Random Forest)
        ↓
Fall Detector (rule engine, stateful — tracks rolling window of recent poses)
        ↓
Inactivity Detector (stateful — tracks time since last significant movement)
        ↓
Event Decision:
  • Activity changed → close previous activities row, open new one
  • Fall confirmed / inactivity threshold hit → create alert, capture screenshot,
    trigger email/telegram/alarm
        ↓
Push to WebSocket (skeleton overlay coords, activity label, confidence, FPS, alert flags)
```

**Camera management:** `camera_manager.py` supports webcam index, USB device, IP camera HTTP stream, and RTSP URL through the same `cv2.VideoCapture(source)` call, with the source string/index coming from the `camera_settings` table. It includes reconnect-on-failure logic (bonus feature: auto-reconnect) — if frame grab fails repeatedly, it logs a `camera_disconnected` event and retries with backoff rather than crashing the worker.

**Why fall/inactivity detection is a rule engine, not another ML model:** per the report's own algorithm (Ch. 5) and the fall-detection logic I formalized in Step 1, this is deterministic biomechanical reasoning (angle + velocity + duration thresholds) rather than a pattern the classifier needs to learn — it's more explainable and tunable (all thresholds live in `system_settings`, stored in `system_settings`, exposed by the `/settings` API; the Settings page was removed from the UI) than a black-box model would be for a safety-critical trigger.

---

## 7. REST API Design

All routes prefixed `/api/v1`. Full request/response schemas will be finalized in Step 10, but the surface is:

| Group | Endpoints (illustrative) |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/register` (admin-only), `POST /auth/refresh`, `POST /auth/forgot-password` |
| Patients | `GET/POST /patients`, `GET/PUT/DELETE /patients/{id}` |
| Activities | `GET /activities/current`, `GET /activities/history?patient_id=&from=&to=` |
| Alerts | `GET /alerts`, `PATCH /alerts/{id}/resolve`, `GET /alerts/{id}/screenshot` |
| Reports | `POST /reports/generate`, `GET /reports`, `GET /reports/{id}/download` |
| Analytics | `GET /analytics/activity-distribution`, `GET /analytics/weekly-trend`, `GET /analytics/fall-frequency` |
| Camera | `GET /camera/status`, `POST /camera/start`, `POST /camera/stop`, `PUT /camera/settings` |
| Settings | `GET/PUT /settings` |
| Realtime | `WS /ws/live` |

All routes except `/auth/login` and `/auth/register` require a valid JWT bearer token; role checks (e.g., only admin can hit `/settings` or `/camera/settings`) are enforced via a FastAPI dependency (`api/deps.py::require_role("admin")`).

---

## 8. Authentication Architecture

- **Password storage:** bcrypt hashing (via `passlib`) — never plaintext, never reversible encryption.
- **Tokens:** JWT access tokens (short-lived, e.g., 30–60 min) signed with a server-side secret (`SECRET_KEY` from `.env`); optional refresh token (longer-lived) for "remember me" without forcing re-login every hour.
- **Roles:** `admin` (full access: settings, camera config, user management) and `caregiver` (dashboard, live monitor, patients, alerts, reports — no system settings).
- **Forgot password:** token-based reset flow — a time-limited reset token emailed to the user, consumed once to set a new password. (Requires the same email service used for alerts, so it's built on shared infrastructure, not a separate system.)
- **Frontend enforcement:** `AuthContext` stores the token in memory + a secure storage mechanism appropriate for a real deployed web app (httpOnly cookie or equivalent — not `localStorage`, to reduce XSS token-theft risk), and `ProtectedRoute`/role checks hide UI the user isn't authorized to reach; the backend is the actual source of truth for authorization regardless of what the UI shows.

---

## 9. Deployment Architecture

```
docker-compose.yml
 ├── backend service   (FastAPI + Uvicorn, exposes :8000, mounts uploads/ and models_store/ as volumes)
 ├── frontend service  (Vite build served via Nginx, exposes :80, proxies /api → backend)
 └── (optional) db service (Postgres, if not using file-based SQLite)
```

- **Dev mode:** `uvicorn app.main:app --reload` + `npm run dev` (Vite dev server with proxy to backend) — fastest iteration loop.
- **Production-style demo:** `docker-compose up --build` — one command brings up both services, matching the "one-click installation" goal.
- **Camera access in Docker:** documented caveat — webcam passthrough into a Linux container requires `--device=/dev/video0`; this will be called out explicitly in the README/installation guide rather than silently assumed, since it's a common real-world gotcha for this exact kind of project.
- **Environment config:** `.env.example` documents every required variable (DB URL, JWT secret, email SMTP creds, Telegram bot token, default thresholds) so the app never has hardcoded secrets.

---

## Summary of module responsibilities

| Module | Single responsibility |
|---|---|
| `api/*` | HTTP contract only |
| `services/*` | Business rules |
| `models/*` | DB schema |
| `schemas/*` | I/O validation |
| `camera/*` | Frame acquisition |
| `ml/*` | Pose → features → activity label |
| `alerts/*` | Notification delivery |
| `pipeline/*` | Orchestrates camera+ml+alerts+db into one continuous loop |
| `frontend/pages` | Screens |
| `frontend/components` | Reusable UI |
| `frontend/services` | API calls |
| `frontend/context` | Cross-cutting state (auth) |

This architecture is what every subsequent step will implement against.
