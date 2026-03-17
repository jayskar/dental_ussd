# Future Roadmap

> This document tracks planned features and improvements for the Dental USSD Application.

---

## 1. SMS Reminders via Celery (Planned)

### Overview

After a patient books an appointment, they should receive an SMS confirmation and reminder. Celery (the task queue) and Redis (the message broker) are already installed in `requirements.txt` — this feature is the next logical step.

### Architecture

```
book_appointment()  →  send_sms_reminder.delay(phone, details)  →  Celery Worker  →  SMS Gateway API
                                    ↑
                              Redis (broker)
```

1. `book_appointment()` in `utils.py` dispatches a Celery task asynchronously after creating the appointment.
2. The Celery worker (a separate process) picks up the task from the Redis queue.
3. The worker calls an SMS gateway API (Africa's Talking, Twilio, etc.) to send the reminder.
4. The USSD session is not blocked — the task runs in the background.

### Implementation Sketch

```python
# dental_ussd/tasks.py (new file)
from celery import shared_task
import requests
import structlog

logger = structlog.get_logger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms_reminder(self, phone_number: str, appointment_details: dict):
    """
    Send an SMS appointment confirmation to the patient.
    Retries up to 3 times with a 60-second delay on failure.
    """
    message = (
        f"Your {appointment_details['appointment_type']} appointment at "
        f"{appointment_details['clinic_location']} on "
        f"{appointment_details['appointment_date']} is confirmed."
    )
    try:
        # Example: Africa's Talking API
        response = requests.post(
            'https://api.africastalking.com/version1/messaging',
            headers={'apiKey': settings.AT_API_KEY, 'Content-Type': 'application/x-www-form-urlencoded'},
            data={'username': settings.AT_USERNAME, 'to': phone_number, 'message': message}
        )
        response.raise_for_status()
        logger.info("SMS sent", phone=phone_number[-4:])
    except Exception as exc:
        logger.error("SMS send failed, retrying", error=str(exc))
        raise self.retry(exc=exc)
```

```python
# dental_ussd/utils.py — update book_appointment()
from dental_ussd.tasks import send_sms_reminder
from django.forms.models import model_to_dict

def book_appointment(ussd_request):
    ...
    # After successfully creating the appointment:
    appointment_data = model_to_dict(obj_appointment, fields=['appointment_type', 'clinic_location', 'appointment_date'])
    send_sms_reminder.delay(patient.mobile_number, appointment_data)
    return obj_appointment
```

```python
# dental_app/celery.py (new file)
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dental_app.settings')
app = Celery('dental_app')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

```python
# dental_app/settings.py — add Celery config
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
```

Start a worker:

```bash
celery -A dental_app worker --loglevel=info
```

---

## 2. Appointment Rescheduling

Allow patients to change their appointment date/time via USSD without cancelling and rebooking.

**Proposed USSD flow:**

```
Main Menu → Reschedule Appointment → List scheduled appointments
         → Select appointment → Show new available slots
         → Confirm new slot → Update appointment record
```

**Implementation notes:**
- Add a `reschedule_appointment` utility function
- Add corresponding YAML screens to the journey file
- The existing `ClinicAvailability` query logic can be reused
- Restore the old slot's `available_slots` when rescheduling

---

## 3. PostgreSQL Migration

Move from SQLite to PostgreSQL for production scalability and concurrent write support.

**Why**: SQLite does not support multiple concurrent writers. With multiple Gunicorn workers, write-heavy operations (booking, cancellation) can cause `OperationalError: database is locked`.

**Steps**: See [docs/05b_deployment_production.md](05b_deployment_production.md#migrating-to-postgresql).

---

## 4. Rate Limiting (Per Phone Number)

The current DRF `AnonRateThrottle` limits by IP address. A USSD gateway typically sends all requests from a single IP, so per-IP limiting is ineffective.

**Proposed solution**: Implement per-phone-number rate limiting using `django-ratelimit`:

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='post:phoneNumber', rate='10/m', method='POST', block=True)
def post(self, request):
    ...
```

This limits each phone number to 10 requests per minute — sufficient for legitimate USSD use and effective against scripted abuse.

---

## 5. Patient Profile Update

Allow patients to update their name via USSD without going through the admin panel.

**Proposed USSD flow:**

```
Main Menu → My Profile → Update Name → Enter new name → Confirm → Update Patient record
```

---

## 6. Multi-language Support

The `language` field is already accepted in the API request and passed to `CustomUssdRequest`. The YAML journey could be made multi-language using Jinja2 template variables that select language-specific strings from the session.

**Proposed approach:**
- Accept `language` from the request (`en`, `fr`, `sw`, etc.)
- Store in session at the start of the journey
- Use a translation dict loaded by a `function_screen` at the start
- Reference translated strings in screen text: `{{ translations.welcome }}`

---

## 7. Appointment Confirmation SMS

Related to the Celery feature (#1). In addition to a reminder, send an SMS immediately when an appointment is booked:

- `send_sms_reminder.delay()` — fires after booking, sends confirmation now
- A second scheduled task could fire 24 hours before the appointment date

---

## 8. Admin Dashboard Improvements

The current Django Admin is functional but minimal. Planned improvements:

- **Filters**: Filter appointments by date range, not just status
- **Search**: Full-text search across patient names, phone numbers, and clinic locations
- **Bulk actions**: Mark multiple appointments as "done" in one click
- **Dashboard widgets**: Today's appointments count, available slots count, registration count this week
- Consider `django-grappelli` or `django-unfold` for a modern admin UI

---

## 9. API Documentation UI

`drf-spectacular` is already installed and configured. Expose the Swagger UI and ReDoc:

```python
# dental_app/urls.py
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    ...
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
```

Once added, the interactive API documentation will be available at `/api/schema/swagger-ui/`.

---

← [Previous: Vue Simulator](08_vue_simulator.md) | [Back to README](../README.md)
