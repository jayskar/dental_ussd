# Vue.js USSD Simulator (Local Testing Only)

> ⚠️ **WARNING: This simulator is for LOCAL DEVELOPMENT ONLY.**  
> Do not expose the simulator in a production environment. It has no authentication and is designed solely to mimic a USSD phone interface for local testing.

---

## 1. What is the USSD Simulator?

The USSD simulator is a Vue.js single-page application that renders a virtual mobile phone screen in your browser. It lets you interact with the USSD backend exactly as a real phone would — navigating menus, entering text, and seeing responses — without needing a real telco or USSD gateway.

This makes it the easiest way to test the full USSD flow locally.

---

## 2. Repository

The simulator lives in a separate repository, on the `mydev` branch:

**<https://github.com/jayskar/ussd-simulator/tree/mydev>**

Always use the `mydev` branch — it contains the configuration needed to work with this project.

---

## 3. Prerequisites

| Tool | Minimum Version | Check |
|---|---|---|
| Node.js | 16+ | `node --version` |
| npm | 7+ | `npm --version` |

**Install Node.js:**

- **macOS**: `brew install node`
- **Linux (Ubuntu)**: `sudo apt install nodejs npm`
- **Windows**: Download from [nodejs.org](https://nodejs.org/)

---

## 4. Setup Steps

```bash
# Clone the simulator repository
git clone https://github.com/jayskar/ussd-simulator.git
cd ussd-simulator

# Switch to the mydev branch
git checkout mydev

# Navigate to the Vue app directory
cd ussd-mock

# Install dependencies
npm install

# Start the development server
npm run serve
```

The simulator will start at `http://localhost:8081`. Open this URL in your browser.

---

## 5. Connecting to the Django Backend

The simulator sends requests to the Django USSD endpoint. For this to work from a browser, Django must include CORS headers allowing the simulator's origin.

The `settings.py` is already configured for this:

```python
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:8081,http://127.0.0.1:8081',
    cast=Csv()
)
```

As long as your `.env` includes `http://localhost:8081` in `CORS_ALLOWED_ORIGINS` (the default), the simulator can communicate with Django without any additional configuration.

---

## 6. Configuration

### Changing the Backend URL

If Django runs on a different port (e.g. `8001` instead of `8000`), update the backend URL in the simulator's configuration.

Look for the API endpoint setting in `ussd-mock/src/` — typically in a `.env` file or a config file at the root of the `ussd-mock` directory:

```bash
# ussd-mock/.env (create if it doesn't exist)
VUE_APP_API_URL=http://localhost:8001/dental_ussd/dental_ussd_gw/
```

Then rebuild the simulator:

```bash
npm run serve
```

### Running the Simulator via Docker

The simulator is also available as a Docker service in `docker-compose.yml`. To start it with Docker:

```bash
docker compose up simulator
```

The simulator will be available at `http://localhost:8081` (or the port set in `SIMULATOR_PORT`).

> **Token authentication**: The Docker simulator build bakes a DRF token into the JS bundle. To set this, create a DRF token first:
> ```bash
> docker compose exec web python manage.py drf_create_token <your-superuser-username>
> ```
> Then set `VUE_APP_AUTH_TOKEN=<token>` in `.env` and rebuild: `docker compose build simulator`.

---

## 7. Running Both Together

1. **Start Django first**:

   ```bash
   # In terminal 1
   source venv/bin/activate
   python manage.py runserver
   ```

2. **Start the simulator** (in a second terminal):

   ```bash
   # In terminal 2
   cd ussd-simulator/ussd-mock
   npm run serve
   ```

3. **Open the simulator**: Navigate to `http://localhost:8081` in your browser.

You should see a virtual mobile phone. Enter a phone number to begin a USSD session.

---

## 8. Example Test Flow — Booking an Appointment

Follow these steps in the simulator UI:

### Step 1: Enter a Phone Number

In the simulator's phone number field, enter: `+67570001111`

Click **Dial** or press Enter to send the initial request.

**Expected**: The screen shows the non-authenticated menu (if this number isn't registered yet):

```
Welcome! No Profile found.
1. Register (Enter Name)
2. Exit
```

### Step 2: Register

Type `1` and press **Send**.

**Expected**:
```
Enter Full Name
```

### Step 3: Enter Your Name

Type your name (e.g. `Jane Smith`) and press **Send**.

**Expected**:
```
Registration success, name: Jane Smith.
1. Go to main menu
2. Exit
```

### Step 4: Go to Main Menu

Type `1` and press **Send**.

**Expected**:
```
Welcome Jane Smith.
1. Check Appointments
2. Book New Appointment
3. Cancel Appointment
4. Exit
```

### Step 5: Book an Appointment

Type `2` (Book New Appointment) and press **Send**.

**Expected**:
```
Select Appointment Type:
1. Cleaning
2. Checkup
3. Filling
0. Back
```

### Step 6: Select Appointment Type

Type `2` (Checkup) and press **Send**.

**Expected** (if clinic slots are available):
```
Available Slots:
1. City Centre Clinic (2025-06-15 09 AM)
0. Back
```

### Step 7: Select a Slot

Type `1` and press **Send**.

**Expected**:
```
Book Checkup: City Centre Clinic at 2025-06-15 09AM.
1. Confirm
2. Cancel
```

### Step 8: Confirm

Type `1` and press **Send**.

**Expected** (session ends):
```
Appointment Confirmed! You'll get an SMS reminder.
```

The session is terminated (`MSGTYPE: END`). The appointment is now visible in Django Admin under **Appointments**.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `CORS error` in browser console | CORS not configured | Ensure `CORS_ALLOWED_ORIGINS` includes `http://localhost:8081` in `.env` |
| `Network Error` / no response | Django server not running | Start `python manage.py runserver` first |
| `TypeError: Cannot read property` | Wrong `mydev` branch | Run `git checkout mydev` in the simulator repo |
| Blank screen in simulator | Node version too old | Upgrade to Node.js 16+ |

---

← [Previous: Known Bugs](07_known_bugs.md) | [Back to README](../README.md) | [Next: Future Roadmap →](09_future_roadmap.md)
