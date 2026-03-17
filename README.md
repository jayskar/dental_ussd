# Dental Appointment USSD Application

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Django](https://img.shields.io/badge/django-5.2.1-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

A USSD-based dental appointment booking system built with Django and the open-source `ussd_airflow_engine`. Patients can book, view, and cancel appointments directly from their mobile phone by dialling a USSD shortcode — no internet or smartphone required.

---

## Features

- 📱 **USSD interface** — works on any mobile phone, no app needed
- 📅 **Book appointments** — browse available slots by type (Checkup, Cleaning, Filling, Extraction)
- 📋 **Check appointments** — list all past and upcoming appointments
- ❌ **Cancel appointments** — cancel scheduled appointments via USSD menu
- 🔐 **Patient registration** — automatic registration on first dial
- 🛠️ **Django Admin panel** — manage patients, appointments, and clinic availability
- 🐳 **Docker support** — single `docker compose up` for local development

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Runtime |
| Django | 5.2.1 | Web framework |
| Django REST Framework | 3.16.0 | APIView, serialisers, throttling |
| ussd_airflow_engine | custom fork | USSD session and journey management |
| Redis | 7 (alpine) | Session store and cache backend |
| Celery | 5.5.2 | Task queue (planned: SMS reminders) |
| WhiteNoise | 6.12.0 | Static file serving |
| Gunicorn | 25.1.0 | WSGI production server |
| SQLite | — | Development database |
| python-decouple | 3.8 | Environment variable management |
| structlog | 25.3.0 | Structured logging |
| drf-spectacular | 0.29.0 | OpenAPI schema generation |

---

## Quick Start (3 steps)

```bash
# 1. Clone and set up environment
git clone https://github.com/jayskar/dental_ussd.git
cd dental_ussd
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure and migrate
cp .env.example .env   # edit .env with your values
python manage.py migrate
python manage.py createsuperuser

# 3. Start Redis, then run the server
redis-server &
python manage.py runserver
```

👉 For full setup instructions including Redis, fixtures, and curl testing, see **[docs/02_quickstart.md](docs/02_quickstart.md)**.

---

## Documentation

| File | Description |
|---|---|
| [docs/01_architecture.md](docs/01_architecture.md) | System architecture, DRF, USSD engine internals, models, session management |
| [docs/02_quickstart.md](docs/02_quickstart.md) | Step-by-step local development setup guide |
| [docs/03_api_reference.md](docs/03_api_reference.md) | Full API endpoint reference with request/response examples |
| [docs/04_journey_engine.md](docs/04_journey_engine.md) | YAML journey engine deep dive — screen types, session keys, walkthrough |
| [docs/05a_deployment_tutorial.md](docs/05a_deployment_tutorial.md) | Beginner-friendly deployment tutorial (VPS + Docker) |
| [docs/05b_deployment_production.md](docs/05b_deployment_production.md) | Production-hardened deployment reference (Nginx, Gunicorn, SSL) |
| [docs/06_security.md](docs/06_security.md) | Security model, USSD endpoint security, env vars, Redis, admin hardening |
| [docs/07_known_bugs.md](docs/07_known_bugs.md) | Tracked bugs with severity, impact, workarounds, and fixes |
| [docs/08_vue_simulator.md](docs/08_vue_simulator.md) | Vue.js USSD simulator setup for local testing |
| [docs/09_future_roadmap.md](docs/09_future_roadmap.md) | Planned features: SMS reminders, PostgreSQL, rate limiting, and more |

---

## Repository Structure

```
dental_ussd/
├── dental_app/               # Django project configuration
│   ├── settings.py           # All Django/DRF/Redis settings
│   ├── urls.py               # Root URL configuration
│   ├── wsgi.py               # WSGI application entry point
│   └── asgi.py               # ASGI application entry point
├── dental_ussd/              # Main Django application
│   ├── models.py             # Patient, Appointment, ClinicAvailability
│   ├── views.py              # DentalAppUssdGateway (APIView)
│   ├── utils.py              # USSD business logic functions
│   ├── admin.py              # Django Admin registrations
│   ├── urls.py               # App URL configuration
│   └── migrations/           # Database migrations
├── journeys/
│   └── dental_appointment_menu.yml  # USSD screen journey definition
├── fixtures/
│   └── sample_data.json      # Sample clinic availability data
├── docs/                     # Full documentation suite
├── Dockerfile                # Multi-stage Docker build
├── Dockerfile.simulator      # Vue.js simulator Docker build
├── docker-compose.yml        # Docker Compose (web + Redis + simulator)
├── docker-entrypoint.sh      # Container startup script
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
└── manage.py                 # Django management script
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes and add tests where applicable
4. Ensure existing tests pass (`python manage.py test`)
5. Submit a pull request targeting the `main` branch

Please keep pull requests focused and include a clear description of what changes were made and why.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
