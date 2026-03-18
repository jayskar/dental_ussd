# API Reference

> **Codebase reference**: `dental_ussd/views.py` — `DentalAppUssdGateway`

---

## Endpoint

### `POST /dental_ussd/dental_ussd_gw/`

The single USSD gateway endpoint. Receives a POST request from a USSD gateway and returns a USSD response.

**Authentication**: `Authorization: Token <token>` header required (see [docs/authentication.md](authentication.md)).  
**CSRF**: Exempt.  
**Rate limit**: 60 requests per minute (anonymous).

---

## Request

### Headers

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `Authorization` | `Token <your-drf-token>` |

### Request Fields

| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `sessionId` | string | ✅ Yes | Unique session identifier assigned by the USSD gateway for this session. Must be non-empty. | `"sess-abc123"` |
| `phoneNumber` | string | ✅ Yes | Caller's phone number in E.164 format (optional leading `+`, 9–15 digits). | `"+67570001111"` |
| `MSG` | string | ✅ Yes | Full USSD input string from the user (the complete dial string, e.g. `*1*2`). Empty string on the initial dial. Max 200 characters. | `"*1*2"` |
| `serviceCode` | string | ✅ Yes | The USSD service code dialled by the user. Use `"test"` to receive `MSGTYPE: "TEST"` instead of `CON`/`END`. | `"*123#"` |
| `language` | string | No | Preferred language code. Default: `"en"`. | `"en"` |
| `use_built_in_session_management` | boolean | No | When `true`, the engine manages the session ID internally (uses `None` as the session key). Default: `false`. | `false` |

---

## Response

### Response Fields

| Field | Type | Description |
|---|---|---|
| `status` | string | `"success"` on a successful response, `"error"` if the request was invalid. |
| `MSG` | string | The USSD message text to display on the user's phone. |
| `MSGTYPE` | string | `"CON"` — session continues (show menu, wait for input). `"END"` — session terminated. `"TEST"` — when `serviceCode` is `"test"`. |

### HTTP Status Codes

| Code | Meaning |
|---|---|
| `200 OK` | Request processed successfully. |
| `400 Bad Request` | Missing required field, invalid phone number format, or MSG too long. |

---

## Example Requests and Responses

### 1. Initial Dial — Unregistered User

```bash
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "sess-001",
    "phoneNumber": "+67570001111",
    "MSG": "",
    "serviceCode": "*123#"
  }'
```

```json
{
    "status": "success",
    "MSG": "Welcome! No Profile found.\n1. Register (Enter Name)\n2. Exit",
    "MSGTYPE": "CON"
}
```

---

### 2. Initial Dial — Registered User

```bash
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "sess-002",
    "phoneNumber": "+67570002222",
    "MSG": "",
    "serviceCode": "*123#"
  }'
```

```json
{
    "status": "success",
    "MSG": "Welcome Jane Smith.\n1. Check Appointments\n2. Book New Appointment\n3. Cancel Appointment\n4. Exit",
    "MSGTYPE": "CON"
}
```

---

### 3. Registration Flow — Enter Name

First, select option 1 (Register) from the non-authenticated menu:

```bash
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "sess-001",
    "phoneNumber": "+67570001111",
    "MSG": "*1",
    "serviceCode": "*123#"
  }'
```

```json
{
    "status": "success",
    "MSG": "Enter Full Name",
    "MSGTYPE": "CON"
}
```

Submit the name:

```bash
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "sess-001",
    "phoneNumber": "+67570001111",
    "MSG": "*1*John Doe",
    "serviceCode": "*123#"
  }'
```

```json
{
    "status": "success",
    "MSG": "Registration success, name: John Doe.\n1. Go to main menu\n2. Exit",
    "MSGTYPE": "CON"
}
```

---

### 4. Booking an Appointment

From the authenticated menu, select option 2 (Book New Appointment):

```bash
# Select "Book New Appointment"
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-002","phoneNumber":"+67570002222","MSG":"*2","serviceCode":"*123#"}'
```

```json
{
    "status": "success",
    "MSG": "Select Appointment Type:\n1. Cleaning\n2. Checkup\n3. Filling\n0. Back",
    "MSGTYPE": "CON"
}
```

Select appointment type:

```bash
# Select "Checkup" (option 2)
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-002","phoneNumber":"+67570002222","MSG":"*2*2","serviceCode":"*123#"}'
```

```json
{
    "status": "success",
    "MSG": "Available Slots:\n1. City Centre Clinic (2025-06-15 09 AM)\n2. North Branch (2025-06-16 02 PM)",
    "MSGTYPE": "CON"
}
```

Select a slot and confirm:

```bash
# Select slot 1
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-002","phoneNumber":"+67570002222","MSG":"*2*2*1","serviceCode":"*123#"}'
```

```json
{
    "status": "success",
    "MSG": "Book Checkup: City Centre Clinic at 2025-06-15 09AM.\n1. Confirm\n2. Cancel",
    "MSGTYPE": "CON"
}
```

Confirm booking:

```bash
# Confirm (option 1)
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-002","phoneNumber":"+67570002222","MSG":"*2*2*1*1","serviceCode":"*123#"}'
```

```json
{
    "status": "success",
    "MSG": "Appointment Confirmed! You'll get an SMS reminder.",
    "MSGTYPE": "END"
}
```

---

### 5. Checking Appointments

```bash
# Select "Check Appointments" (option 1) from authenticated menu
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-003","phoneNumber":"+67570002222","MSG":"*1","serviceCode":"*123#"}'
```

```json
{
    "status": "success",
    "MSG": "Your Appointments:\n1. Checkup on 15/06/2025 (scheduled)\n2. Cleaning on 20/06/2025 (done)\n0. Back",
    "MSGTYPE": "CON"
}
```

No appointments:

```json
{
    "status": "success",
    "MSG": "You have no appointments.\n1. Book Appointment\n2. Exit",
    "MSGTYPE": "CON"
}
```

---

### 6. Cancelling an Appointment

```bash
# Select "Cancel Appointment" (option 3) from authenticated menu
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-004","phoneNumber":"+67570002222","MSG":"*3","serviceCode":"*123#"}'
```

```json
{
    "status": "success",
    "MSG": "My Scheduled Appointments:\n1. Checkup on 15/06/2025\n0. Back",
    "MSGTYPE": "CON"
}
```

Select appointment to cancel and confirm:

```bash
# Select appointment 1
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-004","phoneNumber":"+67570002222","MSG":"*3*1","serviceCode":"*123#"}'
```

```json
{
    "status": "success",
    "MSG": "Cancel Checkup: City Centre Clinic at 2025-06-15 09AM.\n1. Cancel Appointment\n0. Back",
    "MSGTYPE": "CON"
}
```

```bash
# Confirm cancellation
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-004","phoneNumber":"+67570002222","MSG":"*3*1*1","serviceCode":"*123#"}'
```

```json
{
    "status": "success",
    "MSG": "Your appointment has been cancelled successfully.",
    "MSGTYPE": "END"
}
```

---

### 7. Error Response — Missing Field

```bash
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-001","phoneNumber":"+67570001111"}'
```

```json
{
    "status": "error",
    "MSG": "Missing required field: MSG; Missing required field: serviceCode",
    "MSGTYPE": "END"
}
```

**HTTP Status**: `400 Bad Request`

---

## OPTIONS — CORS Preflight

### `OPTIONS /dental_ussd/dental_ussd_gw/`

Handles CORS preflight requests from the Vue simulator. Returns allowed methods and sets CORS headers.

```json
{
    "status": "success",
    "message": "Allowed methods: GET, POST, OPTIONS",
    "allowed_methods": ["GET", "POST", "OPTIONS"]
}
```

CORS response headers include:

```
Access-Control-Allow-Origin: http://localhost:8081
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Credentials: true
```

---

## `serviceCode: "test"` Mode

When `serviceCode` is set to `"test"`, the response uses `MSGTYPE: "TEST"` instead of `"CON"` or `"END"`. This is useful for integration testing scripts that want to distinguish test traffic from live traffic.

```bash
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"sess-t1","phoneNumber":"+67570001111","MSG":"","serviceCode":"test"}'
```

```json
{
    "status": "success",
    "MSG": "Welcome! No Profile found.\n1. Register (Enter Name)\n2. Exit",
    "MSGTYPE": "TEST"
}
```

---

← [Previous: Quick Start](02_quickstart.md) | [Back to README](../README.md) | [Next: Journey Engine →](04_journey_engine.md)
