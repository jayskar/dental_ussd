# Architecture

> **Codebase reference**: Django 5.2.1, DRF 3.16.0, ussd_airflow_engine (custom fork), Redis 7, SQLite.

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Request Flow                               │
│                                                                     │
│  Mobile Phone                                                       │
│      │  (dials *XXX#)                                               │
│      ▼                                                              │
│  Telco Network                                                      │
│      │  (USSD protocol)                                             │
│      ▼                                                              │
│  USSD Gateway  (e.g. Africa's Talking, Comviva)                     │
│      │  POST /dental_ussd/dental_ussd_gw/                          │
│      ▼                                                              │
│  Django  ──  DentalAppUssdGateway (APIView, csrf_exempt, IsAuthenticated) │
│      │                                                              │
│      ├──► Input validation & sanitisation (_validate_request)       │
│      │                                                              │
│      ├──► CustomUssdRequest  ─────────────────────────────────────►│
│      │        (phone_number, session_id, ussd_input, journey_name)  │
│      │                                                              │
│      ├──► UssdEngine.ussd_dispatcher()                              │
│      │        │                                                      │
│      │        ├──► YAML Journey File                                │
│      │        │    (journeys/dental_appointment_menu.yml)            │
│      │        │                                                      │
│      │        ├──► Utils Functions                                  │
│      │        │    (dental_ussd/utils.py)                           │
│      │        │         │                                           │
│      │        │         └──► Database  (SQLite / PostgreSQL)        │
│      │        │                                                      │
│      │        └──► Redis Session  (read / write session data)       │
│      │                                                              │
│      └──► Response  {"status","MSG","MSGTYPE":"CON"|"END"}          │
│              │                                                      │
│          USSD Gateway  ──►  Telco  ──►  Mobile Phone               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Django Project Structure

The repository contains two distinct Django layers:

### `dental_app/` — Project Configuration

| File | Purpose |
|---|---|
| `settings.py` | All Django settings (installed apps, middleware, database, Redis, DRF, CORS, USSD journey path) |
| `urls.py` | Root URL router — mounts `admin/` and includes `dental_ussd.urls` under `dental_ussd/` |
| `wsgi.py` | WSGI entry point for Gunicorn and other WSGI servers |
| `asgi.py` | ASGI entry point (for future async support) |

### `dental_ussd/` — Application Logic

| File | Purpose |
|---|---|
| `models.py` | `Patient`, `Appointment`, `ClinicAvailability` database models |
| `views.py` | `DentalAppUssdGateway` — the single USSD endpoint handler |
| `utils.py` | Business logic functions called by the YAML journey engine |
| `admin.py` | Django Admin registrations for all three models |
| `urls.py` | App-level URL patterns — maps `dental_ussd_gw/` to the gateway view |
| `migrations/` | Django database migration files |

---

## 3. Django REST Framework (DRF)

### What DRF Is

Django REST Framework is a toolkit for building Web APIs on top of Django. It provides serialisers, authentication backends, permission classes, throttling, and response renderers.

### How `APIView` Works

`DentalAppUssdGateway` extends `APIView`. When a request arrives, DRF runs the authentication, permission, and throttle checks defined on the view before calling the appropriate HTTP method handler (`post()`, `options()`, etc.).

### Token Authentication on the USSD Endpoint

```python
class DentalAppUssdGateway(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]
```

Every caller — whether a real telco USSD gateway or the local Vue.js simulator — must authenticate with a DRF token. A Django user account is created for each gateway, a token is generated with `python manage.py drf_create_token <username>`, and the gateway is configured to send:

```
Authorization: Token <token>
```

See [docs/authentication.md](authentication.md) for a step-by-step guide.

### Why `csrf_exempt` Is Used

USSD gateways POST to the endpoint without a Django CSRF token in the request headers. The `@method_decorator(csrf_exempt, name='dispatch')` decorator disables CSRF verification for this view. This is safe because:

1. The USSD gateway is the only caller (IP allowlisting can enforce this).
2. There is no browser session or cookie that CSRF is designed to protect.

### Token Authentication Configuration

`TokenAuthentication` is the authentication class used by `DentalAppUssdGateway`. Every request must include an `Authorization: Token <token>` header. Requests without a valid token are rejected with `401 Unauthorized`.

---

## 4. USSD Airflow Engine

### What It Is

`ussd_airflow_engine` (installed as the `ussd` package) is an open-source Python library for managing USSD session state through YAML-defined "journey" files. The custom fork used by this project is at <https://github.com/jayskar/ussd_engine>.

It provides:
- `UssdRequest` — a request object carrying phone number, session ID, and user input
- `UssdEngine` — the dispatcher that reads the journey YAML and advances through screens

### `UssdEngine` and `UssdRequest`

```python
ussd_request = CustomUssdRequest(
    phone_number="67570001111",
    session_id="sess-abc123",
    ussd_input="1",
    service_code="*123#",
    language="en",
    journey_name="simple_patient_journey"
)
ussd_engine = UssdEngine(ussd_request)
ussd_response = ussd_engine.ussd_dispatcher()
```

`ussd_dispatcher()` returns a `UssdResponse` object. `str(ussd_response)` gives the text to display on the phone. `ussd_response.status` is `True` for `CON` (continue) and `False` for `END`.

### `CustomUssdRequest`

`CustomUssdRequest` (in `dental_ussd/views.py`) extends `UssdRequest` by overriding `get_screens()`:

```python
class CustomUssdRequest(UssdRequest):
    def get_screens(self, screen_name=None):
        journey_file = getattr(self, 'journey_file', settings.DEFAULT_USSD_SCREEN_JOURNEY)
        with open(journey_file, 'r') as f:
            journey_content = yaml.safe_load(f)
        return journey_content.get(screen_name)
```

This replaces the engine's default screen loader with one that reads screens from the project's YAML file at `journeys/dental_appointment_menu.yml`.

### `journey_name` and `DEFAULT_USSD_SCREEN_JOURNEY`

`journey_name` is passed to `UssdRequest` and used internally by the engine as a Redis namespace for sessions (so different journeys don't collide). `DEFAULT_USSD_SCREEN_JOURNEY` in `settings.py` is the filesystem path to the YAML file:

```python
DEFAULT_USSD_SCREEN_JOURNEY = os.path.join(BASE_DIR, 'journeys', 'dental_appointment_menu.yml')
```

---

## 5. YAML Journey Processing — Step-by-Step Walkthrough

### Step 1: POST Arrives at `DentalAppUssdGateway.post()`

A USSD gateway sends a `POST /dental_ussd/dental_ussd_gw/` request with a JSON body containing `sessionId`, `phoneNumber`, `MSG`, and `serviceCode`.

### Step 2: Input Parsing from `MSG`

The `MSG` field contains the full USSD dial string (e.g. `*123#*1*2`). The view splits on `*` and takes the last element as the current user input:

```python
list_of_inputs = sanitised['MSG'].split('*')
text = list_of_inputs[-1]  # "2" in the example above
```

A special case handles a trailing `**` (user pressed `*` as input).

### Step 3: `CustomUssdRequest` Construction

```python
ussd_request = CustomUssdRequest(
    phone_number=sanitised['phoneNumber'].strip('+'),
    session_id=session_id,
    ussd_input=text,
    service_code=sanitised['serviceCode'],
    language=sanitised['language'],
    journey_name="simple_patient_journey"
)
```

The phone number has its leading `+` stripped to use as a Redis key-safe identifier.

### Step 4: `UssdEngine` Initialised and `ussd_dispatcher()` Called

```python
ussd_engine = UssdEngine(ussd_request)
ussd_response = ussd_engine.ussd_dispatcher()
```

### Step 5: Engine Reads `initial_screen` from YAML

The engine loads the YAML and reads `initial_screen: authenticate_user`. On the first request in a session, it starts at `authenticate_user`.

### Step 6: `function_screen` — Call Python Function, Store in Session

```yaml
authenticate_user:
  type: function_screen
  function: dental_ussd.utils.authenticate_user
  session_key: patient
  next_screen: router_1
```

The engine calls `dental_ussd.utils.authenticate_user(ussd_request)`. The return value is stored in `ussd_request.session['patient']` under the key `patient`. The engine then moves to `router_1`.

### Step 7: `router_screen` — Evaluate Jinja2 Expression

```yaml
router_1:
  type: router_screen
  default_next_screen: authenticated_menu
  router_options:
    - expression: "{{ patient == None }}"
      next_screen: non_authenticated_menu
```

The engine evaluates `{{ patient == None }}` against the current session. If `True`, it navigates to `non_authenticated_menu`. Otherwise it falls through to the `default_next_screen`: `authenticated_menu`.

### Step 8: `menu_screen` / `input_screen` — Render and Return `CON`

Menu and input screens render their text, build numbered option lists, and return a `CON` response (the session continues, waiting for user input on the next request).

### Step 9: `quit_screen` — Return `END`

```yaml
end:
  type: quit_screen
  text: Thank you for using our service. Goodbye!
```

A `quit_screen` always returns a `False` status (mapped to `MSGTYPE: END`), terminating the USSD session.

### Step 10: Response Formatting

```python
msg_type = 'CON' if ussd_response.status else 'END'
response_data = {
    'status': 'success',
    'MSG': str(ussd_response),
    'MSGTYPE': msg_type
}
```

The gateway forwards `MSG` to the phone and either continues the session (`CON`) or closes it (`END`).

---

## 6. Session Management

Sessions are backed by Redis and use Django's JSON serialiser (safer than the default pickle-based serialiser):

```python
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        ...
    }
}
```

The `phone_number` is stored in the session at the start of every journey and used by all utility functions to identify the patient:

```python
phone_number = ussd_request.session.get('phone_number')
```

Session data flows between screens by reading and writing keys on `ussd_request.session`. Each `function_screen` stores its return value under `session_key`. Subsequent screens access that value via Jinja2 template syntax (e.g. `{{ patient.name }}`).

---

## 7. Data Models

```
┌──────────────────────────────┐         ┌───────────────────────────────┐
│           Patient            │         │         Appointment           │
├──────────────────────────────┤         ├───────────────────────────────┤
│ id              BigAutoField │◄────────│ patient_id    FK → Patient    │
│ mobile_number   CharField(15)│  1:many │ appointment_type  CharField   │
│ name            CharField    │         │ clinic_location   CharField   │
│ created_at      DateTimeField│         │ appointment_date  DateTimeField│
│ updated_at      DateTimeField│         │ status            CharField   │
└──────────────────────────────┘         │ created_at        DateTimeField│
                                         │ updated_at        DateTimeField│
                                         └───────────────────────────────┘

┌───────────────────────────────────┐
│         ClinicAvailability        │
├───────────────────────────────────┤
│ id               BigAutoField     │
│ clinic_location  CharField(100)   │
│ appointment_type CharField(20)    │
│ available_slots  IntegerField ≥ 0 │
│ appointment_date DateTimeField    │
│ updated_at       DateTimeField    │
└───────────────────────────────────┘
```

### Patient

| Field | Type | Constraints |
|---|---|---|
| `id` | BigAutoField | PK, auto-generated |
| `mobile_number` | CharField(15) | unique, not null, regex `^\+?\d{9,15}$` |
| `name` | CharField(100) | not null |
| `created_at` | DateTimeField | auto set on create |
| `updated_at` | DateTimeField | auto updated |

### Appointment

| Field | Type | Constraints |
|---|---|---|
| `id` | BigAutoField | PK |
| `patient` | ForeignKey(Patient) | CASCADE delete |
| `appointment_type` | CharField(50) | choices: Checkup, Cleaning, Filling, Extraction |
| `clinic_location` | CharField(100) | not null |
| `appointment_date` | DateTimeField | not null |
| `status` | CharField(20) | choices: scheduled, done, cancelled; default: scheduled |
| `created_at` | DateTimeField | auto |
| `updated_at` | DateTimeField | auto |

### ClinicAvailability

| Field | Type | Constraints |
|---|---|---|
| `id` | BigAutoField | PK |
| `clinic_location` | CharField(100) | not null |
| `appointment_type` | CharField(20) | choices: Checkup, Cleaning, Filling, Extraction; default: checkup |
| `available_slots` | IntegerField | ≥ 0 (DB constraint + MinValueValidator) |
| `appointment_date` | DateTimeField | not null |
| `updated_at` | DateTimeField | auto updated |

---

## 8. Key Dependencies

| Package | Version | Purpose |
|---|---|---|
| Django | 5.2.1 | Web framework and ORM |
| djangorestframework | 3.16.0 | APIView, authentication, permissions, throttling |
| ussd_airflow_engine | custom fork | USSD session and YAML journey engine |
| django-redis | 5.4.0 | Redis cache backend for Django |
| redis | 6.1.0 | Python Redis client |
| PyYAML | 6.0.2 | YAML journey file parsing |
| Jinja2 | 3.1.6 | Template expressions in router/menu screens |
| structlog | 25.3.0 | Structured, machine-readable logging |
| python-decouple | 3.8 | Environment variable loading from `.env` |
| django-cors-headers | 4.9.0 | CORS headers for Vue simulator |
| whitenoise | 6.12.0 | Static file serving in production |
| gunicorn | 25.1.0 | WSGI server |
| drf-spectacular | 0.29.0 | OpenAPI schema auto-generation |
| celery | 5.5.2 | Task queue (planned: SMS reminders) |
| django-annoying | 0.10.8 | `get_object_or_None` utility |

---

← [Back to README](../README.md) | [Next: Quick Start →](02_quickstart.md)
