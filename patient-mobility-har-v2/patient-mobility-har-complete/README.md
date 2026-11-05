# MobilityWatch — AI-Based Human Activity Recognition System for Patient Mobility Assessment

A camera-only, non-intrusive patient monitoring platform that uses computer vision and machine learning to recognize patient activities in real time, detect falls and prolonged inactivity, alert caregivers, and generate mobility reports — without requiring any wearable device.

Built as a full-stack reference implementation: FastAPI + SQLAlchemy backend, React + TypeScript frontend, MediaPipe pose estimation, and a Random Forest activity classifier.

---

## Features

- **Real-time activity recognition** — walking, standing, sitting, lying, classified from MediaPipe pose landmarks via a Random Forest model
- **Fall detection** — two-stage rule engine (sudden-onset trigger + sustained-posture confirmation) tuned to avoid false alarms from quick bends/sits
- **Prolonged inactivity detection** — configurable threshold, aware that "lying still" is often expected (e.g. sleeping) rather than a warning sign
- **Live monitoring dashboard** — WebSocket-streamed video with pose-skeleton overlay, glassmorphism UI, dark mode
- **Alerts** — in-app + automatic email to each caregiver assigned to the patient (setup: [docs/email_alerts.md](docs/email_alerts.md)) + optional Telegram/SMS/WhatsApp, with automatic screenshot capture on confirmed events
- **Patient management** — full CRUD with photos, medical notes, room/doctor/emergency-contact tracking
- **Reports** — daily/weekly/monthly, in PDF (with embedded charts + activity timeline), CSV, or XLSX (with native editable Excel charts)
- **Analytics** — activity distribution, weekly trend, fall frequency, average walking time
- **Role-based auth** — JWT, admin vs. caregiver permissions
- **Camera flexibility** — webcam, USB, IP, or RTSP sources, with reconnect-with-backoff on failure

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, JWT |
| Computer vision | OpenCV, MediaPipe Pose |
| Machine learning | scikit-learn (Random Forest), joblib |
| Database | SQLite (dev), PostgreSQL-ready |
| Frontend | React, Vite, TypeScript, TailwindCSS, ShadCN-style components, Recharts, Framer Motion |
| Reports | ReportLab (PDF), openpyxl (XLSX), matplotlib (chart rendering) |
| Deployment | Docker, docker-compose, GitHub Actions CI |

## Quick start (Docker)

```bash
cp .env.example .env      # fill in SECRET_KEY and DEFAULT_ADMIN_PASSWORD at minimum
docker-compose up --build
```
- Frontend: http://localhost
- Backend API + Swagger docs: http://localhost:8000/docs
- Default admin login: the email/password you set in `.env`

For local (non-Docker) development, model training, and camera setup, see **[docs/installation_guide.md](docs/installation_guide.md)**.
For production deployment considerations (Postgres, HTTPS, camera passthrough, secrets), see **[docs/deployment_guide.md](docs/deployment_guide.md)**.

## Project structure

```
patient-mobility-har/
├── backend/            FastAPI app, ML pipeline, camera manager, tests
├── frontend/            React dashboard
├── docs/                 Architecture, folder structure, installation, deployment, API docs
├── .github/workflows/  CI pipeline
├── docker-compose.yml
└── .env.example
```
See [docs/architecture.md](docs/architecture.md) and [docs/folder_structure.md](docs/folder_structure.md) for the full design writeup this project was built from.

## Running tests

```bash
cd backend
pytest -v
```

## Training the activity classifier

The repository ships only a **synthetic placeholder** activity model (no real people; its metrics are not evidence of accuracy).
Build a real multi-subject dataset and train with subject-wise evaluation as described in
[docs/activity_recognition.md](docs/activity_recognition.md):

```bash
cd backend
python -m app.ml.data.extract_features_from_clips   # after recording/adding clips
python -m app.ml.train_model                        # real data; add --synthetic only for a placeholder
```

## License

This project is provided as an academic/portfolio reference implementation. Adapt licensing as appropriate for your use case before any clinical deployment — see the note in the deployment guide on regulatory considerations for real patient data.
