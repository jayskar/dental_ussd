# YAML Journey Engine Deep Dive

> **Codebase references**: `journeys/dental_appointment_menu.yml`, `dental_ussd/views.py` (`CustomUssdRequest`), `dental_ussd/utils.py`.  
> **Engine source**: <https://github.com/jayskar/ussd_engine>

---

## 1. What is ussd_airflow_engine?

`ussd_airflow_engine` is an open-source Python library for building USSD applications. Instead of writing imperative Python code to manage each menu screen and session state, you define your entire USSD flow in a YAML file — called a "journey" — and the engine takes care of:

- Advancing through screens based on user input
- Evaluating conditional routing expressions
- Calling Python functions at designated steps
- Storing and retrieving session data between requests

The custom fork used by this project is pinned at <https://github.com/jayskar/ussd_engine>.

---

## 2. Screen Types

The journey YAML is a dictionary where each key is a screen name. The `type` field determines how the engine processes that screen.

### `function_screen`

Calls a Python function and stores the return value in the session.

```yaml
authenticate_user:
  type: function_screen
  function: dental_ussd.utils.authenticate_user   # dotted Python path
  session_key: patient                             # key to store the return value under
  next_screen: router_1                            # always moves here after execution
```

| Field | Description |
|---|---|
| `function` | Fully qualified Python callable path. The function receives `ussd_request` as its only argument. |
| `session_key` | The session dictionary key under which the function's return value is stored. |
| `next_screen` | The screen to navigate to after the function completes. |

A `function_screen` does **not** render any text to the user. It executes silently and immediately moves to `next_screen`.

---

### `router_screen`

Evaluates Jinja2 expressions against the current session and selects the next screen.

```yaml
router_1:
  type: router_screen
  default_next_screen: authenticated_menu          # used if no expression matches
  router_options:
    - expression: "{{ patient == None }}"          # Jinja2 expression
      next_screen: non_authenticated_menu
```

| Field | Description |
|---|---|
| `default_next_screen` | Used when no `router_options` expression evaluates to `True`. |
| `router_options` | List of `{expression, next_screen}` pairs. Evaluated in order. First match wins. |
| `expression` | A Jinja2 boolean expression. The session dict is the template context. |

The engine evaluates expressions in order. The **first** expression that renders to a truthy value determines `next_screen`. If none match, `default_next_screen` is used.

> ⚠️ **Known issue (BUG-003)**: Earlier versions of the journey YAML used `condition:` instead of `expression:`. The engine only recognises `expression:`. See [docs/07_known_bugs.md](07_known_bugs.md#bug-003).

---

### `menu_screen`

Renders a numbered list of options and waits for user input. Returns `CON`.

```yaml
authenticated_menu:
  type: menu_screen
  text: |
    Welcome {{patient.name}}.
  options:
    - text: Check Appointments
      next_screen: check_all_appointments
    - text: Book New Appointment
      next_screen: book_appointment
    - text: Exit
      next_screen: end
```

**Static options** (`options` list):

| Field | Description |
|---|---|
| `text` | Jinja2 template string rendered as a numbered option. |
| `next_screen` | Screen to navigate to when the user selects this option. |
| `input_value` | Optional. If set, the option is only selectable when the user enters this exact value. |

**Dynamic options** (`items` dict) — generated from a Python dict stored in the session:

```yaml
show_appointments:
  type: menu_screen
  text: |
    Your Appointments:
  items:
    text: "{{value}}"               # displayed text (the dict value)
    value: "{{key}}"                # stored value (the dict key)
    with_dict: "{{ all_appointments }}"  # session key holding the dict
    session_key: appointment        # where to store the selected key
    next_screen: fetch_selected_appointment
  options:
    - text: Back
      input_value: "0"
      next_screen: authenticated_menu
```

When the user selects a dynamically-generated item, the item's `value` (the dict key) is stored in the session under `session_key`.

---

### `input_screen`

Displays a prompt and stores the user's raw text input in the session.

```yaml
enter_name:
  type: input_screen
  text: Enter Full Name
  input_identifier: patient_name    # session key to store the input under
  next_screen: register_user
```

| Field | Description |
|---|---|
| `text` | Prompt text displayed to the user. |
| `input_identifier` | Session key under which the raw input is stored. |
| `next_screen` | Screen to navigate to after input is received. |

---

### `quit_screen`

Displays a message and terminates the session. Returns `END`.

```yaml
end:
  type: quit_screen
  text: Thank you for using our service. Goodbye!
```

| Field | Description |
|---|---|
| `text` | Final message shown to the user. The session is terminated after this screen. |

---

## 3. `initial_screen`

The `initial_screen` key at the top of the YAML tells the engine which screen to start on for a new session:

```yaml
initial_screen: authenticate_user
```

On the **first** request of a session, the engine starts at `authenticate_user`. On subsequent requests, it resumes from wherever the session left off.

---

## 4. Session Key Mechanics

Every `function_screen` stores its return value under `session_key`. Subsequent screens can access that value in Jinja2 template expressions:

```
authenticate_user  →  stores return value as  session['patient']
router_1           →  evaluates  {{ patient == None }}
authenticated_menu →  renders    Welcome {{patient.name}}.
```

The session is a plain Python dictionary backed by Redis. All values must be JSON-serialisable (the project uses `JSONSerializer`). Return complex objects as dictionaries (e.g. `model_to_dict()`), not Django model instances.

---

## 5. Dynamic Menus with `with_dict`

When a `function_screen` returns a Python `dict`, that dict can be used to build a numbered menu using `with_dict`:

```python
# utils.py
def check_all_appointments(ussd_request) -> dict | None:
    ...
    return {42: "Checkup on 15/06/2025 (scheduled)", 43: "Cleaning on 20/06/2025 (done)"}
```

```yaml
# YAML
check_all_appointments:
  type: function_screen
  function: dental_ussd.utils.check_all_appointments
  session_key: all_appointments
  next_screen: check_all_appointment_response

show_appointments:
  type: menu_screen
  text: Your Appointments:
  items:
    text: "{{value}}"
    value: "{{key}}"
    with_dict: "{{ all_appointments }}"
    session_key: appointment
    next_screen: fetch_selected_appointment
```

The engine iterates the dict and renders:
```
Your Appointments:
1. Checkup on 15/06/2025 (scheduled)    ← dict value
2. Cleaning on 20/06/2025 (done)         ← dict value
```

When the user selects option `1`, the engine stores `42` (the dict key) in `session['appointment']`.

---

## 6. Annotated Walkthrough of `dental_appointment_menu.yml`

### Booking Flow

```
initial_screen: authenticate_user
      │
      ▼
[function_screen] authenticate_user
  → calls utils.authenticate_user(ussd_request)
  → stores Patient instance (or None) as session['patient']
  → next: router_1
      │
      ▼
[router_screen] router_1
  → if {{ patient == None }} → non_authenticated_menu
  → else                     → authenticated_menu
      │
      ├─── [menu_screen] non_authenticated_menu
      │         → option 1: Register → enter_name
      │         → option 2: Exit     → end
      │              │
      │         [input_screen] enter_name
      │              → stores input as session['patient_name']
      │              → next: register_user
      │                   │
      │         [function_screen] register_user
      │              → calls utils.register_user(ussd_request)
      │              → creates Patient record
      │              → next: register_confirmation
      │                   │
      │         [menu_screen] register_confirmation
      │              → option 1: Go to main menu → authenticated_menu
      │              → option 2: Exit            → end
      │
      └─── [menu_screen] authenticated_menu
                → option 1: Check Appointments  → check_all_appointments
                → option 2: Book New Appointment → book_appointment
                → option 3: Cancel Appointment  → cancel_an_appointment
                → option 4: Exit               → end
```

**Booking sub-flow:**

```
[menu_screen] book_appointment
  → items from static dict {cleaning, checkup, filling}
  → stores selected key as session['appointment_type']
  → next: fetch_available_slots
      │
[function_screen] fetch_available_slots
  → calls utils.fetch_available_appointment_slot(ussd_request)
  → stores {pk: "location (date)"} dict as session['appointment_slots']
  → next: check_book_appointment_response
      │
[router_screen] check_book_appointment_response
  → if {{ appointment_slots == None }} → no_available_book_appointment
  → else                               → show_available_slots
      │
[menu_screen] show_available_slots
  → dynamic menu from session['appointment_slots']
  → stores selected slot PK as session['appointment_slot']
  → next: save_slot_key
      │
[function_screen] save_slot_key
  → calls utils.save_appointment_slot(ussd_request)
  → fetches ClinicAvailability by PK, formats as dict
  → stores as session['confirm_appointment_slot']
  → next: book_cleaning_slot_confirm
      │
[menu_screen] book_cleaning_slot_confirm
  → shows: "Book Checkup: City Centre Clinic at 2025-06-15 09AM."
  → option 1: Confirm → function_book_appointment
  → option 2: Cancel  → end
      │
[function_screen] function_book_appointment
  → calls utils.book_appointment(ussd_request)
  → creates Appointment, decrements ClinicAvailability.available_slots
  → next: book_cleaning_slot (quit screen)
      │
[quit_screen] book_cleaning_slot
  → "Appointment Confirmed! You'll get an SMS reminder."
  → END
```

### Cancellation Flow

```
[function_screen] cancel_an_appointment
  → calls utils.get_scheduled_appointments(ussd_request)
  → stores {pk: "type on date"} dict as session['appointment_list']
  → next: check_appointment_response
      │
[router_screen] check_appointment_response
  → if {{ appointment_list == None }} → no_appointments
  → else                              → display_scheduled_appointments
      │
[menu_screen] display_scheduled_appointments
  → dynamic menu from session['appointment_list']
  → stores selected PK as session['selected_appointment']
  → next: save_scheduled_appointment_slot_key
      │
[function_screen] save_scheduled_appointment_slot_key
  → fetches Appointment by PK, verifies ownership
  → stores formatted dict as session['confirm_appointment_slot']
  → next: confirm_cancel_appointment
      │
[menu_screen] confirm_cancel_appointment
  → shows appointment details
  → option 1: Cancel Appointment → cancel_appointment
  → option 0: Back               → display_scheduled_appointments
      │
[function_screen] cancel_appointment
  → calls utils.cancel_appointment(ussd_request)
  → sets appointment.status = 'cancelled'
  → next: appointment_cancelled
      │
[quit_screen] appointment_cancelled
  → "Your appointment has been cancelled successfully."
  → END
```

---

## 7. How to Add a New Appointment Type

1. **Add the choice to the model** (`dental_ussd/models.py`):

```python
APPOINTMENT_TYPE_CHOICES = [
    ('Checkup', 'Checkup'),
    ('Cleaning', 'Cleaning'),
    ('Filling', 'Filling'),
    ('Extraction', 'Extraction'),
    ('Whitening', 'Whitening'),   # ← add here
]
```

2. **Create and apply a migration**:

```bash
python manage.py makemigrations
python manage.py migrate
```

3. **Add the option to the `book_appointment` screen** (`journeys/dental_appointment_menu.yml`):

```yaml
book_appointment:
  type: menu_screen
  text: Select Appointment Type:
  items:
    ...
    with_dict:
      cleaning: Cleaning
      checkup: Checkup
      filling: Filling
      whitening: Whitening   # ← add here
```

4. **`fetch_available_appointment_slot` already handles it** — it queries `ClinicAvailability` filtered by `appointment_type.title()`, so any properly capitalised type works automatically.

5. **Add `ClinicAvailability` records** via Django Admin with the new appointment type.

---

## 8. How to Add a New Screen

Use this template:

```yaml
my_new_screen:
  type: menu_screen          # or function_screen / router_screen / input_screen / quit_screen
  text: |
    Screen text here. Can use {{session_key}} for dynamic values.
  options:
    - text: Option One
      next_screen: next_screen_name
    - text: Exit
      next_screen: end
```

**Checklist:**
- [ ] Give the screen a unique name (snake_case)
- [ ] Add `next_screen` references to valid screen names
- [ ] If it's a `function_screen`, ensure the Python function exists in `utils.py`
- [ ] If it's a `router_screen`, use `expression:` (not `condition:`)
- [ ] Connect the screen by adding it as a `next_screen` reference in an existing screen
- [ ] Test the flow end-to-end using curl or the Vue simulator

---

← [Previous: API Reference](03_api_reference.md) | [Back to README](../README.md) | [Next: Deployment Tutorial →](05a_deployment_tutorial.md)
