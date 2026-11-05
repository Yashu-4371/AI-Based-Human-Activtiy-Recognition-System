# AI-Based Human Activity Recognition System
## Step 2 — Complete Folder Structure & File Responsibilities

No code in this document — every file listed below with a one-to-three line explanation of its exact responsibility. This is the map every later coding step will fill in.

---

## Root

```
patient-mobility-har/
├── backend/
├── frontend/
├── docs/
├── docker-compose.yml
├── .gitignore
└── README.md
```

| File | Responsibility |
|---|---|
| `docker-compose.yml` | Defines and wires the `backend`, `frontend`, and (optionally) `db` containers, shared volumes for uploads/models, and the network between them. Lets the whole system start with `docker-compose up --build`. |
| `.gitignore` | Excludes `node_modules/`, `__pycache__/`, `.env`, `models_store/*.pkl`, `uploads/`, `venv/` etc. from version control. |
| `README.md` | Project overview, setup instructions, screenshots, and links into `docs/` — the front door for anyone (including examiners) opening the repo. |

---

## `docs/`

```
docs/
├── architecture.md
├── api_documentation.md
└── installation_guide.md
```

| File | Responsibility |
|---|---|
| `architecture.md` | The Step 1 architecture document (already generated). |
| `api_documentation.md` | Human-readable companion to the auto-generated Swagger UI — endpoint list, auth flow, example requests/responses. |
| `installation_guide.md` | Step-by-step local setup (Python/Node versions, `.env` values, camera permissions, Docker caveats). |

---

## `backend/`

```
backend/
├── app/
├── models_store/
├── uploads/
├── tests/
├── requirements.txt
├── .env.example
├── Dockerfile
└── alembic/ (optional, for migrations)
```

| File/Folder | Responsibility |
|---|---|
| `requirements.txt` | Pinned Python dependencies (fastapi, uvicorn, sqlalchemy, pydantic, python-jose, passlib, opencv-python, mediapipe, scikit-learn, joblib, reportlab/openpyxl, python-multipart, websockets, etc.). |
| `.env.example` | Documents every environment variable the app reads (DATABASE_URL, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, SMTP_* , TELEGRAM_BOT_TOKEN, DEFAULT_INACTIVITY_THRESHOLD_SEC) without real secrets. |
| `Dockerfile` | Builds the backend image: installs system deps needed by OpenCV/MediaPipe, installs `requirements.txt`, runs Uvicorn. |
| `models_store/` | Holds trained `.pkl` artifacts (`activity_rf.pkl`, `scaler.pkl`). Empty at checkout; populated by running `train_model.py`. Gitignored. |
| `uploads/` | Runtime-created storage for patient photos, alert screenshots, and generated report files (PDF/CSV/XLSX). Gitignored. |
| `tests/` | Pytest suite (see below). |
| `alembic/` | (Optional, added if/when we outgrow `create_all()`) DB migration scripts for evolving schema without data loss. |

### `backend/app/`

```
app/
├── main.py
├── config.py
├── api/
├── models/
├── schemas/
├── database/
├── services/
├── camera/
├── ml/
├── alerts/
├── pipeline/
└── utils/
```

| File | Responsibility |
|---|---|
| `main.py` | Creates the FastAPI app instance, registers all routers from `api/`, configures CORS, mounts the `uploads/` static directory, wires startup event (init DB, load ML model) and shutdown event (release camera). |
| `config.py` | `Settings` class (Pydantic `BaseSettings`) that loads and validates every `.env` variable in one typed place, imported everywhere else instead of raw `os.environ` calls. |

#### `app/api/` — HTTP layer only

| File | Responsibility |
|---|---|
| `deps.py` | Reusable FastAPI dependencies: `get_db()` (yields a DB session), `get_current_user()` (decodes JWT), `require_role("admin")` (403s non-admins). |
| `auth.py` | Routes: login, register (admin-only), refresh token, forgot/reset password. Calls `auth_service`. |
| `patients.py` | CRUD routes for patient records, including photo upload. Calls `patient_service`. |
| `activities.py` | Routes for current live activity and historical activity queries (with date/patient filters). Calls `activity_service`. |
| `alerts.py` | List alerts, resolve an alert, fetch an alert's screenshot. Calls `alert_service`. |
| `reports.py` | Trigger report generation, list past reports, download a report file. Calls `report_service`. |
| `analytics.py` | Aggregated chart data endpoints (activity distribution, weekly trend, fall frequency). Calls `analytics_service`. |
| `camera.py` | Start/stop the monitoring worker, get camera status, update camera source settings. |
| `settings.py` | Get/update system settings (thresholds, email config, alarm sound, theme default) — admin-only. |
| `websocket.py` | `/ws/live` endpoint: accepts a connection, subscribes it to the pipeline's live state, pushes JSON frames (activity label, confidence, skeleton points, FPS, alert flags) until disconnect. |

#### `app/models/` — one SQLAlchemy class per table

| File | Responsibility |
|---|---|
| `user.py` | `User` table definition (id, name, email, password_hash, role, created_at) + relationship to resolved alerts. |
| `patient.py` | `Patient` table definition + relationships to activities, alerts, reports. |
| `activity.py` | `Activity` table definition (per-segment activity rows). |
| `alert.py` | `Alert` table definition (type, priority, status, screenshot path, resolver). |
| `report.py` | `Report` table definition (type, file path, generation timestamp). |
| `camera_setting.py` | `CameraSetting` table definition (source type/URI, resolution, active flag). |
| `system_setting.py` | `SystemSetting` key-value table definition. |
| `log.py` | `Log` table definition for audit/debug trail. |

#### `app/schemas/` — Pydantic I/O contracts, separate from ORM models

| File | Responsibility |
|---|---|
| `user.py` | `UserCreate`, `UserOut`, `UserLogin` — never exposes `password_hash`. |
| `patient.py` | `PatientCreate`, `PatientUpdate`, `PatientOut`. |
| `activity.py` | `ActivityOut`, `ActivityHistoryQuery`. |
| `alert.py` | `AlertOut`, `AlertResolve`. |
| `report.py` | `ReportRequest`, `ReportOut`. |
| `token.py` | `Token`, `TokenPayload` — JWT response and decoded-claims shapes. |

#### `app/database/`

| File | Responsibility |
|---|---|
| `session.py` | Creates the SQLAlchemy `engine` and `SessionLocal` factory from `config.py`'s `DATABASE_URL`; defines the declarative `Base` all models inherit from. |
| `init_db.py` | Called at startup: creates tables if they don't exist, seeds a default admin user if the `users` table is empty (so the app is usable on first run). |

#### `app/services/` — business logic

| File | Responsibility |
|---|---|
| `auth_service.py` | Password hashing/verification, JWT creation/decoding, login logic, password-reset token issuance. |
| `patient_service.py` | Create/update/delete/list patients, handle photo file storage. |
| `activity_service.py` | Query current/historical activities; also called internally by the pipeline to open/close activity segments. |
| `alert_service.py` | Create alerts, mark resolved, fetch screenshots; triggers `alerts/*` notifiers. |
| `report_service.py` | Aggregates activity/alert data for a patient over a period and renders PDF (reportlab), CSV, and XLSX (openpyxl) outputs. |
| `analytics_service.py` | Aggregation queries backing the pie/bar/line charts (activity distribution, weekly/monthly trend, fall frequency, average walking time). |

#### `app/camera/`

| File | Responsibility |
|---|---|
| `camera_manager.py` | Opens a `cv2.VideoCapture` for webcam index / USB / IP / RTSP source from `camera_settings`; handles reconnect-with-backoff on failure; exposes `read_frame()`. |
| `frame_buffer.py` | Thread-safe holder for the most recent frame + derived overlay data, so the HTTP/WebSocket layer never touches OpenCV objects directly. |

#### `app/ml/`

| File | Responsibility |
|---|---|
| `pose_estimator.py` | Wraps MediaPipe Pose; given a frame, returns the 33 landmarks (x, y, z, visibility) or `None` if no person detected. |
| `feature_extractor.py` | Converts raw landmarks into the fixed-length feature vector: joint angles, normalized distances, torso inclination, centroid velocity (needs a short history buffer), bounding-box aspect ratio. |
| `activity_classifier.py` | Loads `models_store/activity_rf.pkl` at startup; exposes `predict(feature_vector) -> (label, confidence)`. |
| `fall_detector.py` | Stateful rule engine implementing the fall logic from the architecture doc (torso angle + vertical velocity + aspect ratio → possible fall; sustained stillness → confirmed fall). |
| `inactivity_detector.py` | Stateful timer per patient tracking time since last significant centroid movement; raises a warning once the configured threshold (30/60/90s) is exceeded. |
| `train_model.py` | Offline script: loads `data/training_features.csv`, trains/evaluates `RandomForestClassifier`, saves the model + scaler to `models_store/`. Not run by the server itself. |
| `data/generate_synthetic_data.py` | Procedurally generates labeled feature rows per activity class using documented biomechanical ranges + noise, writes `training_features.csv`. |
| `data/training_features.csv` | Generated training data (gitignored or committed as a small reproducible sample — decided at generation time). |

#### `app/alerts/`

| File | Responsibility |
|---|---|
| `email_notifier.py` | Sends alert emails via SMTP using credentials from `config.py`; formats a message with patient name, event type, timestamp, and screenshot attachment. |
| `telegram_notifier.py` | Optional: sends a message via the Telegram Bot API if a bot token/chat ID is configured; no-ops cleanly if not configured. |
| `alarm_sound.py` | Server-side hook that flags an alert as "should play alarm"; actual audio playback happens client-side (browser can't be forced to play sound from the server, so this just sets a flag the frontend reacts to) — documented here to avoid a design mismatch later. |

#### `app/pipeline/`

| File | Responsibility |
|---|---|
| `monitoring_worker.py` | The orchestrator: continuous loop that pulls a frame from `camera_manager`, runs it through `pose_estimator → feature_extractor → activity_classifier → fall_detector → inactivity_detector`, decides on activity-segment/alert events, calls the relevant services, and updates `frame_buffer`/WebSocket state. Started/stopped via the `/camera` API. |

#### `app/utils/`

| File | Responsibility |
|---|---|
| `logger.py` | Configures a rotating file + console logger used across the app. |
| `security.py` | Low-level helpers (token generation, constant-time comparisons) used by `auth_service`. |
| `file_storage.py` | Resolves and creates file paths under `uploads/` for photos, screenshots, and reports; keeps path logic in one place. |

### `backend/tests/`

```
tests/
├── test_auth.py
├── test_patients.py
├── test_activities.py
├── test_alerts.py
├── test_fall_detector.py
└── test_feature_extractor.py
```

| File | Responsibility |
|---|---|
| `test_auth.py` | Login success/failure, token validation, role enforcement. |
| `test_patients.py` | CRUD endpoint correctness and validation errors. |
| `test_activities.py` | Activity history query filtering/pagination. |
| `test_alerts.py` | Alert creation and resolve-flow correctness. |
| `test_fall_detector.py` | Feeds synthetic pose sequences and asserts fall/no-fall decisions match expectations — the most important test file, since this is the safety-critical module. |
| `test_feature_extractor.py` | Verifies angle/velocity math against hand-computed expected values for known landmark inputs. |

---

## `frontend/`

```
frontend/
├── src/
├── public/
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── vite.config.ts
├── .env.example
└── Dockerfile
```

| File | Responsibility |
|---|---|
| `package.json` | Dependencies (react, vite, typescript, tailwindcss, shadcn deps, framer-motion, recharts, lucide-react, axios) and npm scripts (dev/build/preview). |
| `tsconfig.json` | TypeScript compiler configuration. |
| `tailwind.config.ts` | Design tokens: hospital blue/white palette, border radius scale, dark-mode strategy. |
| `vite.config.ts` | Dev server proxy (`/api` → backend on :8000), build output config. |
| `.env.example` | `VITE_API_BASE_URL`, `VITE_WS_URL`. |
| `Dockerfile` | Multi-stage build: `npm run build` then serve via Nginx. |

### `frontend/src/`

```
src/
├── main.tsx
├── App.tsx
├── pages/
├── components/
├── hooks/
├── services/
├── context/
├── layouts/
└── assets/
```

| File | Responsibility |
|---|---|
| `main.tsx` | React root render, wraps `App` in `AuthProvider` and router. |
| `App.tsx` | Top-level route definitions, maps paths to pages, applies `ProtectedRoute` where needed. |

#### `src/pages/`

| File | Responsibility |
|---|---|
| `Login.tsx` | Login form, "remember me", forgot-password link; calls `authService`. |
| `Dashboard.tsx` | Overview screen: stat cards, live activity summary, today's alerts, system health, mini live feed preview. |
| `LiveMonitor.tsx` | Full live camera view with skeleton overlay, current activity + confidence badge, start/stop controls. |
| `Patients.tsx` | Patient list/grid with search/filter, add-patient modal trigger. |
| `PatientDetail.tsx` | Single patient's profile, activity timeline, alert history, generate-report button. |
| `Alerts.tsx` | Alert list with priority/status filters, resolve action, screenshot viewer. |
| `Reports.tsx` | Generate/download daily/weekly/monthly reports, past report list. |
| `Analytics.tsx` | Pie/bar/line charts (activity distribution, duration, weekly/monthly trend, fall frequency, avg. walking time). |
| `Settings.tsx` | Camera selection, alert thresholds, email config, alarm sound, theme — admin-only. |

#### `src/components/ui/`
ShadCN primitives generated into the project: `button.tsx`, `card.tsx`, `dialog.tsx`, `table.tsx`, `input.tsx`, `select.tsx`, `badge.tsx`, `tabs.tsx`, `toast.tsx`, `switch.tsx`, `avatar.tsx`. Each is a self-contained, styled, accessible primitive reused across every page instead of one-off styling.

#### `src/components/dashboard/`

| File | Responsibility |
|---|---|
| `StatCard.tsx` | Small animated card showing one metric (e.g., "Today's Alerts: 3"). |
| `ActivityChart.tsx` | Reusable Recharts wrapper configured per chart type used on Dashboard/Analytics. |
| `AlertFeed.tsx` | Scrollable live list of recent alerts, color-coded by priority. |
| `SystemHealthCard.tsx` | Shows camera status, backend connectivity, model load status. |

#### `src/components/camera/`

| File | Responsibility |
|---|---|
| `LiveFeed.tsx` | Renders the video stream (via WebSocket frames or an MJPEG/img-tag endpoint) inside a `<canvas>` or `<img>`. |
| `SkeletonOverlay.tsx` | Draws the pose skeleton on a `<canvas>` layered over the video using the landmark coordinates pushed over WebSocket. |
| `ActivityBadge.tsx` | Shows current activity label + confidence percentage with color coding. |

#### `src/components/patients/`

| File | Responsibility |
|---|---|
| `PatientCard.tsx` | Compact patient summary card for the grid view. |
| `PatientForm.tsx` | Shared add/edit form (name, age, gender, blood group, disease, doctor, room, emergency contact, notes, photo upload). |

#### `src/components/layout/`

| File | Responsibility |
|---|---|
| `Sidebar.tsx` | Main navigation, collapses responsively. |
| `Topbar.tsx` | User menu, dark-mode toggle, notifications bell. |
| `ProtectedRoute.tsx` | Redirects unauthenticated/unauthorized users away from a route. |

#### `src/hooks/`

| File | Responsibility |
|---|---|
| `useAuth.ts` | Convenience hook over `AuthContext`. |
| `useWebSocket.ts` | Manages the `/ws/live` connection lifecycle (connect, reconnect, cleanup) and exposes the latest message. |
| `usePatients.ts` | Fetch/cache patient list for reuse across pages. |

#### `src/services/`

| File | Responsibility |
|---|---|
| `api.ts` | Configured axios instance: base URL, attaches JWT to every request, handles 401 by redirecting to login. |
| `authService.ts` | login/register/refresh/forgot-password API calls. |
| `patientService.ts` | Patient CRUD API calls. |
| `alertService.ts` | Alert list/resolve API calls. |
| `reportService.ts` | Report generation/download API calls. |

#### `src/context/`

| File | Responsibility |
|---|---|
| `AuthContext.tsx` | Holds current user, token, role; provides login/logout functions to the whole tree. |

#### `src/layouts/`

| File | Responsibility |
|---|---|
| `DashboardLayout.tsx` | Wraps all authenticated pages with `Sidebar` + `Topbar` + content outlet. |

#### `src/assets/`
Logo, icons, alarm sound file, illustration images used on the login screen.

---

## File count summary

| Area | Approx. file count |
|---|---|
| Backend `app/` | ~40 files |
| Backend `tests/` | 6 files |
| Frontend `src/` | ~35 files |
| Config/Docker/docs | ~10 files |

This is the exact skeleton Step 2 will scaffold on disk (empty/stub-free — no placeholder functions, per your requirement) once you approve it, and every step after that fills in one coherent slice of it at a time.
