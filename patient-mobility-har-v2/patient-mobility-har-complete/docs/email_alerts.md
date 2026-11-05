# Caregiver Email Alerts — Setup Guide (Windows / VS Code)

When MobilityWatch detects a **fall** or **prolonged inactivity**, it saves the alert and then
**automatically emails the caregivers assigned to that patient**.

## How it works (the short version)

```
Camera → MediaPipe pose → features → activity classifier → fall / inactivity detection
      → alert saved in the database  (Alerts page)
      → backend looks up the patient's assigned caregivers in the database
      → emails each caregiver's SAVED email address
```

* **Who gets the email?** Only caregivers **assigned to that patient** on the Caregivers page, and only
  if they have a valid email saved. The address is read from the database *at the moment of the alert* —
  it is **never** typed into `.env`. Edit a caregiver's email on the Caregivers page and the very next alert uses the new address.
* **Who sends it?** One "sender" Gmail account that you configure once in `backend\.env`. It is only used to send.
* **Safe by design:** if email is not set up, or sending fails, the alert is still saved and monitoring keeps running.
  The same alert is never emailed twice to the same address.

---

## Step 1 — Create a Gmail App Password (for the SENDER account)

Use a Gmail account you control (a dedicated one such as `mobilitywatch.alerts@gmail.com` is best).
Google does not let apps use your normal password; you need a 16-character **App Password**.

1. Sign in to that Google account and open **https://myaccount.google.com/security**.
2. Turn on **2-Step Verification** (required before App Passwords exist).
3. Open **https://myaccount.google.com/apppasswords** (or search "App passwords" in your Google Account settings).
4. Type an app name such as `MobilityWatch` and click **Create**.
5. Google shows a 16-character password like `abcd efgh ijkl mnop`. **Copy it now** — Google won't show it again.

> The App Passwords page is not offered for some work/school accounts or accounts with Advanced Protection.
> In that case use a personal Gmail account as the sender.
> Never share the App Password with anyone, never paste it into chat, and never commit it to Git.

## Step 2 — Enter the sender details in `backend\.env`

Open **`backend\.env`** in VS Code (this is your private config file; it is git-ignored).
Add or edit these lines (copy the block from `backend\.env.example`):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_STARTTLS=true
SMTP_USERNAME=your_sender_gmail@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop
SMTP_FROM_EMAIL=your_sender_gmail@gmail.com
SMTP_FROM_NAME="MobilityWatch Alerts"
```

* `SMTP_USERNAME` and `SMTP_FROM_EMAIL`: the **sender** Gmail address.
* `SMTP_PASSWORD`: the 16-character App Password (spaces are ignored).
* **There is no setting for the recipient.** Do not add one.
* If you leave the placeholder values (`your_sender_gmail@gmail.com`, …) the app treats email as "not configured" and just skips sending.

**Restart the backend** after editing `.env` (Ctrl+C in its terminal, then start it again).

## Step 3 — Add a caregiver and assign them to a patient

1. Log in and open **Patients**; make sure the patient exists.
2. Open **Caregivers → Add Caregiver**.
3. Fill in **Full name**, **Phone**, and the caregiver's **Email** (the address that should receive alerts, e.g. `daughter@gmail.com`).
4. Under **Assigned patients**, tick the patient(s) this caregiver should be told about. **This step matters:**
   a caregiver who is not assigned to a patient is never emailed about that patient.
   (The Caregivers page shows an amber warning on cards that are missing an email or an assignment.)
5. Click **Add Caregiver**. You can assign several caregivers to one patient — all of them are emailed.

## Step 4 — Send a test email (no need to wait for a fall)

As an **admin**, on the Caregivers page click the small **paper-plane icon** on a caregiver's card.
A clearly-labelled TEST email is sent to that caregiver's saved address. If it fails, the message tells you why
(e.g. "rejected the sender login — check SMTP_USERNAME and use a Google App Password").
Check the caregiver's **Spam** folder the first time.

## What the email contains

Subject: `[MobilityWatch] Fall detected — <patient name>` (or "Inactivity warning").
Body: patient name and ID (and room if saved), alert type and priority, date/time of detection (local time with UTC offset),
the alert details recorded by the system, the patient's last recorded activity (only if one exists), a recommendation to check
on the patient, and the MobilityWatch name. The camera screenshot taken at the moment of the alert is attached when available.
Nothing is made up: fields with no recorded value are left out.

## Seeing what happened

* **Alerts page:** each alert shows an email badge — *Email sent to N caregivers*, *Email failed*, or *Email not sent*
  (hover for the reason, e.g. "No caregiver is assigned to this patient").
* **Backend terminal / `backend\logs\app.log`:** lines like `Alert id=7: e-mail SENT to caregiver id=1 (r***@gmail.com)`.
  Addresses are masked and passwords are never logged.

## Troubleshooting

| What you see | Likely cause / fix |
|---|---|
| "Email not sent — No caregiver is assigned to this patient" | Edit the caregiver and tick the patient under *Assigned patients*. |
| "Email not sent — No assigned caregiver has a valid email address" | Add/fix the caregiver's email. |
| "Email not sent — Email (SMTP) is not configured on the server" | Fill in `SMTP_USERNAME` / `SMTP_PASSWORD` in `backend\.env` and restart the backend. |
| "rejected the sender login" | Wrong App Password, or you used the normal Gmail password. Create a new App Password (Step 1). |
| "Could not connect to the email server" | No internet, or a firewall/antivirus blocks `smtp.gmail.com:587`. |
| A second alert did not send an email | Repeat emails to the same address for the same patient and alert type are held back for `ALERT_EMAIL_COOLDOWN_SEC` (default 60 s). The alert is still saved. Set it to `0` to disable. |
| Don't want the screenshot attached | `ALERT_EMAIL_ATTACH_SCREENSHOT=false` |
| Turn all caregiver emails off | `EMAIL_ALERTS_ENABLED=false` |

## Running the project on Windows (PowerShell)

Open the project folder in VS Code, then open two terminals (Terminal → New Terminal).

**Terminal 1 — backend**
```powershell
cd backend
# Optional safety copy of your data before the first run of this version:
Copy-Item patient_mobility.db patient_mobility.backup.db
.\venv\Scripts\Activate.ps1          # if scripts are blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt      # only needed the first time / if you had no venv
uvicorn app.main:app --reload
```
Backend: http://localhost:8000 (API docs at http://localhost:8000/docs).

**Terminal 2 — frontend**
```powershell
cd frontend
npm install                          # first time only
npm run dev
```
Open http://localhost:5173 and log in.

**Run the automated tests** (they never send real emails or messages):
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest -v
```

## Database changes

Nothing to run by hand. On startup the backend creates one **new** table, `alert_email_deliveries`
(a record of which alert was emailed to whom and whether it worked). No existing table, patient, caregiver,
alert or report is modified.

## Good to know

* Automatic detection can be wrong (false alarms and missed events). The email says so. This project is an academic
  reference implementation and is not certified for clinical use.
* The activity classifier shipped with the project was trained on **synthetic** data (see `docs/activity_recognition.md`).
  Email delivery does not depend on it, but detection quality does.
* The old global `ALERT_RECIPIENT_EMAIL` setting was removed: alerts are only emailed to caregivers assigned to the patient.
  If your `.env` still contains that line it is harmlessly ignored.
