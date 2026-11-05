# Installation Guide

This guide covers running the system **locally without Docker** — for the one-command Docker path, see the root [README](../README.md#quick-start-docker). Use this guide when you want to develop, debug, retrain the model, or don't have Docker available.

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.10 works too; earlier versions are untested |
| Node.js | 20+ | Needed for the Vite frontend |
| A webcam | — | Any USB webcam, or an IP/RTSP camera on your network |
| Git | — | To clone the repo |

On Linux, OpenCV/MediaPipe also need a few system libraries:
```bash
sudo apt-get install -y libgl1 libglib2.0-0 libsm6 libxext6 libxrender1
```
macOS and Windows generally don't need this step.

## 1. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configure environment
```bash
cp .env.example .env
```
Open `.env` and set at minimum:
- `SECRET_KEY` — any long random string (used to sign JWTs)
- `DEFAULT_ADMIN_PASSWORD` — the password for the auto-seeded admin account
- `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_FROM_EMAIL` — the *sender* account, only if you want caregiver email alerts; leave blank to skip (alerts still work in-app, email dispatch just no-ops with a log warning). Recipients are the caregivers assigned to the patient — see [email_alerts.md](email_alerts.md)

### Train the activity classifier
The Random Forest model is not committed to the repo (it's a generated artifact) — you must train it once before starting the server:
```bash
python -m app.ml.train_model --synthetic   # placeholder so the app starts; use plain `train_model` once real data exists
```
This will:
1. Load `app/ml/data/training_features.csv` (real data; stops with instructions if missing — use `--synthetic` for a placeholder only)
2. Train a Random Forest classifier and print accuracy/confusion-matrix output
3. Save `models_store/activity_rf.pkl` and `models_store/activity_scaler.pkl`

**Real data:** see [activity_recognition.md](activity_recognition.md) for recording clips, ingesting public datasets, subject-wise evaluation and camera testing. The model is refused at load time if it was trained on a different feature layout.

### Run the backend
```bash
uvicorn app.main:app --reload
```
- API root: http://localhost:8000
- Interactive Swagger docs: http://localhost:8000/docs
- On first startup, the database is created automatically and a default admin user is seeded from your `.env` values.

### Run the test suite (optional but recommended)
```bash
pytest -v
```

## 2. Frontend setup

In a separate terminal:
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```
- Dashboard: http://localhost:5173
- The Vite dev server proxies `/api`, `/uploads`, and `/ws` to `http://localhost:8000` (configured in `vite.config.ts`) — make sure the backend is running first.

Log in with the admin email/password you set in `backend/.env`.

## 3. Camera setup

By default the system uses webcam index `0` (your machine's default camera). To change this:
1. Log in as an admin
2. Go to **Settings → Camera Sources**
3. Edit the source URI:
   - Webcam/USB: a plain integer index (`0`, `1`, ...) — try a few if `0` isn't your intended camera
   - IP camera: the full HTTP stream URL
   - RTSP camera: an `rtsp://` URL, typically including credentials, e.g. `rtsp://user:pass@192.168.1.50:554/stream1`

Then go to **Live Monitor**, select a patient and the camera, and click **Start Monitoring**.

## 4. Common issues

| Symptom | Likely cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'app'` | Run backend commands from inside the `backend/` directory, not the repo root |
| Camera won't open / `Failed to open camera` in logs | Wrong source index — try `1`, `2`, etc., or check the camera isn't in use by another app |
| Activity always shows low confidence / wrong label | You're likely still on the synthetic-data model — train on real recorded data for your actual camera angle/lighting for production accuracy |
| No email alerts arriving | Check `SMTP_*` values in `.env`; Gmail requires an "app password", not your normal account password, if 2FA is enabled |
| Frontend shows "Network Error" on login | Backend isn't running, or is running on a different port than the Vite proxy expects (`8000`) |
| `mediapipe` import error on Apple Silicon | Ensure you're using a `mediapipe` wheel built for `arm64`; some very old versions lack this — upgrade pip first |

For Docker-based deployment instead of this manual setup, see [deployment_guide.md](deployment_guide.md).
