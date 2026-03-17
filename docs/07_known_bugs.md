# Known Bugs and Issues

> Bugs are a normal part of development. This document tracks known issues factually so they can be addressed systematically.
>
> **Codebase reference**: `dental_ussd/utils.py`, `dental_ussd/models.py`, `dental_ussd/views.py`, `journeys/dental_appointment_menu.yml`.

---

## BUG-001: `register_user` tuple unpacking (Fixed)

- **Severity**: Medium
- **Affected File**: `dental_ussd/utils.py`, `register_user()`
- **Status**: ✅ Fixed
- **Description**: `Patient.objects.get_or_create()` returns a tuple `(instance, created)`, not just the instance. An earlier version of the code did not unpack the tuple, making the `if patient is not None` check always `True` (a tuple is never `None`), and the `else` branch unreachable.
- **Impact**: The registration function always appeared to succeed regardless of whether the patient was newly created or already existed. The `created` flag was never checked.
- **Fix applied**:
  ```python
  patient, created = Patient.objects.get_or_create(
      mobile_number=phone_number,
      defaults={'name': patient_name}
  )
  ```

---

## BUG-002: `cancel_appointment` unhandled exception (Fixed)

- **Severity**: High
- **Affected File**: `dental_ussd/utils.py`, `cancel_appointment()`
- **Status**: ✅ Fixed
- **Description**: An earlier version called `Appointment.objects.get(pk=selected_appointment)` without a `try/except` block. If the PK was invalid or the session contained stale data, this raised an unhandled `Appointment.DoesNotExist` exception, crashing the USSD session.
- **Impact**: Any attempt to cancel an appointment with an invalid or expired ID would result in a 500 error visible to the user.
- **Fix applied**: The current implementation wraps the lookup in a `try/except Appointment.DoesNotExist` block and also validates ownership:
  ```python
  try:
      appointment = Appointment.objects.get(
          pk=selected_appointment,
          patient__mobile_number=phone_number,
          status='scheduled'
      )
      appointment.status = 'cancelled'
      appointment.save()
  except Appointment.DoesNotExist:
      logger.error("Appointment not found or not owned by user", ...)
  except Exception as e:
      logger.error("Error cancelling appointment", ...)
  ```

---

## BUG-003: Journey YAML `router_screen` used `condition:` instead of `expression:`

- **Severity**: High
- **Affected File**: `journeys/dental_appointment_menu.yml`
- **Status**: ✅ Fixed
- **Description**: The `ussd_airflow_engine` expects router options to use the key `expression:` for Jinja2 expressions. An earlier version of the YAML used `condition:` which the engine does not recognise, causing the router to always fall through to `default_next_screen` regardless of the session data.
- **Impact**: The `check_appointment_response` router always navigated to `display_scheduled_appointments` even when there were no scheduled appointments, causing an empty menu to be shown.
- **Fix applied**: All `router_options` entries now correctly use `expression:`:
  ```yaml
  router_options:
    - expression: "{{ appointment_list == None }}"
      next_screen: no_appointments
  ```

---

## BUG-004: `get_appointments` screen referenced non-existent function

- **Severity**: Low
- **Affected File**: `journeys/dental_appointment_menu.yml` (earlier revision)
- **Status**: ✅ Fixed
- **Description**: An earlier version of the YAML contained a `get_appointments` screen that referenced `dental_ussd.utils.get_all_appointments`, a function that did not exist in `utils.py`. Additionally, the screen was never linked from any other screen (`next_screen`), making it dead code.
- **Impact**: Would have raised an `AttributeError` if the screen were ever reached, crashing the USSD session.
- **Fix applied**: The dead screen was removed. The active appointment-checking flow uses `check_all_appointments` (in `utils.py`) and `check_all_appointment_response` (in the YAML), which are correctly implemented.

---

## BUG-005: `fetch_scheduled_appointment` orphaned screen

- **Severity**: Low
- **Affected File**: `journeys/dental_appointment_menu.yml` (earlier revision)
- **Status**: ✅ Fixed
- **Description**: A `fetch_scheduled_appointment` screen was defined in the YAML but was never referenced as a `next_screen` by any other screen — dead code.
- **Impact**: No runtime impact (unreachable). Caused confusion during development about the intended flow.
- **Fix applied**: The orphaned screen was removed from the current YAML.

---

## BUG-006: `Patient.mobile_number` max_length too short

- **Severity**: Medium
- **Affected File**: `dental_ussd/models.py`, `Patient.mobile_number`
- **Status**: ✅ Fixed
- **Description**: An earlier version set `max_length=11`, which cannot hold international E.164 numbers. E.164 allows up to 15 digits plus an optional `+` prefix (16 characters total).
- **Impact**: Attempting to register a patient with a phone number longer than 11 characters would raise a `DataError` (PostgreSQL) or silently truncate (SQLite).
- **Fix applied**: `max_length=15` is now set, and a `RegexValidator` enforces the E.164 format:
  ```python
  mobile_number = models.CharField(
      max_length=15,
      null=False,
      unique=True,
      validators=[phone_validator]
  )
  ```

---

## BUG-007: Dead utility functions — `book_cleaning`, `book_checkup`, `book_filling`, `book_cleaning_slot`

- **Severity**: Low
- **Affected File**: `dental_ussd/utils.py`
- **Status**: Open (marked deprecated, not yet removed)
- **Description**: Four functions — `book_cleaning()`, `book_checkup()`, `book_filling()`, and `book_cleaning_slot()` — are not referenced by any YAML screen and duplicate the logic of `fetch_available_appointment_slot()` and `book_appointment()`.
- **Impact**: No runtime impact. Adds confusion about the intended code paths and increases maintenance burden.
- **Workaround**: The functions are marked with a `# DEPRECATED` comment in the current codebase. They should not be called in new code.
- **Fix**: Remove all four functions in a future cleanup PR. Verify no external code calls them before removing.

---

## BUG-008: `print()` statements in production code

- **Severity**: Medium
- **Affected File**: `dental_ussd/utils.py` (earlier revision)
- **Status**: ✅ Fixed
- **Description**: Multiple `print()` calls in `utils.py` (in `authenticate_user`, `register_user`, `book_appointment`, `get_scheduled_appointments`, `cancel_appointment`, and others) output sensitive data including phone numbers and appointment details to stdout.
- **Impact**: In production, stdout typically goes to the server logs or Docker logs, making sensitive PII visible to anyone with log access.
- **Fix applied**: All `print()` calls have been replaced with `structlog` `logger.info()` / `logger.error()` calls using structured keyword arguments.

---

## BUG-009: `book_cleaning_slot` never decrements available slots

- **Severity**: Medium
- **Affected File**: `dental_ussd/utils.py`, `book_cleaning_slot()`
- **Status**: Open (function is deprecated — see BUG-007)
- **Description**: Unlike `book_appointment()`, the `book_cleaning_slot()` function creates an `Appointment` record but never decrements `ClinicAvailability.available_slots`. This would allow overbooking if the function were called.
- **Impact**: No runtime impact currently, as `book_cleaning_slot()` is dead code (not referenced in the YAML). However, if someone were to reference it, it would silently overbook.
- **Workaround**: The function is unreachable from the YAML. Use `book_appointment()` for all appointment creation.
- **Fix**: Remove `book_cleaning_slot()` as part of the BUG-007 cleanup.

---

## BUG-010: `fetch_selected_appointment` session key consistency

- **Severity**: Low
- **Affected File**: `dental_ussd/utils.py`, `fetch_selected_appointment()`; `journeys/dental_appointment_menu.yml`
- **Status**: Open (investigate)
- **Description**: The `fetch_selected_appointment()` utility reads `ussd_request.session.get('appointment')`. The YAML `show_appointments` screen stores the selected appointment ID under `session_key: appointment` in the `items` config. This is consistent. However, the `fetch_selected_appointment` function_screen then stores its result as `session_key: selected_appointment`. The `display_selected_appointment` quit screen uses `{{ selected_appointment }}`. The chain appears correct, but the naming is close enough to `selected_appointment` (used in the cancel flow) to cause confusion.
- **Impact**: No confirmed bug. The naming overlap between the "view appointment" flow (`appointment` → `selected_appointment`) and the "cancel appointment" flow (`selected_appointment`) could cause session data collisions if both flows run in the same session.
- **Workaround**: The flows are navigated from separate menu options and do not intersect in normal usage.
- **Fix**: Rename session keys to be more descriptive — e.g. `viewed_appointment_id` vs `cancel_appointment_id` — in a future refactor.

---

← [Previous: Security](06_security.md) | [Back to README](../README.md) | [Next: Vue Simulator →](08_vue_simulator.md)
