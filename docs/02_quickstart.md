# Quick Start — Local Development

> **Goal**: Get the Dental USSD app running on your local machine, ready to test with the Vue simulator or curl.

---

## Prerequisites

Before you begin, make sure you have the following installed:

| Tool | Minimum Version | Check |
|---|---|---|
| Python | 3.12+ | `python3 --version` |
| Redis | 6+ | `redis-server --version` |
| Git | any | `git --version` |

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/jayskar/dental_ussd.git
cd dental_ussd
```

---

## Step 2: Create and Activate a Virtual Environment

A virtual environment keeps the project's dependencies isolated from your system Python.

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```bat
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

You should see `(venv)` at the start of your terminal prompt.

---

## Step 3: Copy `.env.example` to `.env` and Fill In Values

```bash
cp .env.example .env
```

Open `.env` in your editor and set the following values:

| Variable | Example | Description |
|---|---|---|
| `SECRET_KEY` | `django-dev-key-change-me` | Django secret key. Use any random string for development. |
| `DEBUG` | `True` | Enable debug mode. **Never `True` in production.** |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated list of allowed hosts. |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis connection URL. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:8081` | Origins allowed for CORS (Vue simulator URL). |
| `ANON_THROTTLE_RATE` | `60/minute` | Rate limit for unauthenticated requests. |

**Example `.env` for local development:**

```ini
SECRET_KEY=django-dev-key-change-me-for-local-use
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
REDIS_URL=redis://127.0.0.1:6379/0
CORS_ALLOWED_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
ANON_THROTTLE_RATE=60/minute
```

---

## Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note**: One dependency (`ussd_airflow_engine`) is installed directly from GitHub, so Git must be available. If installation fails, make sure `git` is on your `PATH`.

---

## Step 5: Run Database Migrations

```bash
python manage.py migrate
```

This creates the SQLite database file `db.sqlite3` and applies all migrations, creating the `Patient`, `Appointment`, and `ClinicAvailability` tables.

---

## Step 6: Create a Superuser

You'll need a superuser account to access the Django Admin panel.

```bash
python manage.py createsuperuser
```

Enter a username, email (optional), and password when prompted.

---

## Step 7: Start Redis

The app uses Redis for session storage. Start Redis before running the Django server.

**macOS (Homebrew):**
```bash
brew services start redis
# or run in foreground:
redis-server
```

**Linux (systemd):**
```bash
sudo systemctl start redis
# Check it's running:
redis-cli ping   # should print: PONG
```

**Windows:**
Redis is not officially supported on Windows. Use one of these options:
- [WSL2](https://docs.microsoft.com/en-us/windows/wsl/install) — install Redis inside Ubuntu on WSL2
- [Redis Stack on Docker](https://hub.docker.com/r/redis/redis-stack): `docker run -p 6379:6379 redis:7-alpine`

---

## Step 8: Run the Development Server

```bash
python manage.py runserver
```

The server starts at `http://127.0.0.1:8000/`. You should see:

```
System check identified no issues.
Django version 5.2.1, using settings 'dental_app.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

---

## Step 9: Load Sample Fixture Data

The app ships with sample `ClinicAvailability` records so you can start testing immediately.

```bash
python manage.py loaddata fixtures/sample_data.json
```

This creates several clinic availability slots of different appointment types. You can view and add more via the Django Admin.

---

## Step 10: Add Clinic Availability via Django Admin

1. Open `http://127.0.0.1:8000/admin/` in your browser.
2. Log in with the superuser credentials you created in Step 6.
3. Click **Clinic availabilitys** (under **Dental Ussd**).
4. Click **Add Clinic Availability** and fill in:
   - **Clinic location**: e.g. `City Centre Clinic`
   - **Appointment type**: e.g. `Checkup`
   - **Available slots**: e.g. `5`
   - **Appointment date**: a future date and time
5. Click **Save**.

Repeat to create slots for different appointment types and locations.

---

## Step 11: Test with curl

Once the server is running and you have fixture data loaded, test the USSD endpoint directly:

**Initial dial (new session, no previous input):**

```bash
curl -s -X POST http://127.0.0.1:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-session-001",
    "phoneNumber": "+67570001111",
    "MSG": "",
    "serviceCode": "*123#"
  }' | python3 -m json.tool
```

**Expected response (unregistered user):**

```json
{
    "status": "success",
    "MSG": "Welcome! No Profile found.\n1. Register (Enter Name)\n2. Exit",
    "MSGTYPE": "CON"
}
```

**Select option 1 (Register):**

```bash
curl -s -X POST http://127.0.0.1:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-session-001",
    "phoneNumber": "+67570001111",
    "MSG": "*1",
    "serviceCode": "*123#"
  }' | python3 -m json.tool
```

**Expected:**

```json
{
    "status": "success",
    "MSG": "Enter Full Name",
    "MSGTYPE": "CON"
}
```

---

## Step 12: Django Admin Walkthrough

The Django Admin gives you full visibility into your data:

| Section | What you can do |
|---|---|
| **Patients** | View registered patients, search by name or phone number |
| **Appointments** | View all appointments, filter by status or type, see patient details |
| **Clinic Availabilitys** | Add/edit clinic slots, set available count and date |

To view a patient's appointments, click the patient record and scroll to the related appointments section.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `redis.exceptions.ConnectionError` | Redis isn't running | Start Redis (Step 7) |
| `ModuleNotFoundError: No module named 'ussd'` | Dependencies not installed | Run `pip install -r requirements.txt` |
| `django.db.utils.OperationalError: no such table` | Migrations not run | Run `python manage.py migrate` |
| `ImproperlyConfigured: SECRET_KEY must be set` | Missing `.env` or wrong DEBUG value | Copy `.env.example` to `.env` and set `DEBUG=True` |

---

← [Previous: Architecture](01_architecture.md) | [Back to README](../README.md) | [Next: API Reference →](03_api_reference.md)
