# Authentication Guide

The Dental USSD API uses **DRF Token Authentication** for all requests. Every caller — whether a real telco USSD gateway or the local Vue.js simulator — must be registered as a Django user and must present a valid DRF token on every request.

---

## Authentication Model

| Concept | Detail |
|---------|--------|
| Mechanism | `rest_framework.authentication.TokenAuthentication` |
| Header | `Authorization: Token <token>` |
| Scope | Every caller has its own Django user account and token |
| Examples | Airtel gateway user, Safaricom gateway user, local simulator user |

Each telco gateway that connects to the API is created as a separate Django user. A DRF token is generated for that user and configured in the gateway's HTTP client. The gateway sends the token on every request.

---

## Creating a Gateway User

### Option A — Django Admin

1. Log in to Django Admin at `http://localhost:8000/admin/`
2. Go to **Authentication and Authorization → Users → Add user**
3. Set a username (e.g. `airtel_gateway`) and a strong password
4. Save the user

### Option B — Django Shell

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
User.objects.create_user(username='airtel_gateway', password='strong-password-here')
```

---

## Generating a DRF Token

Run the following management command after creating the user:

```bash
python manage.py drf_create_token <username>
```

Example:

```bash
python manage.py drf_create_token airtel_gateway
# Output: Generated token abc123def456... for user airtel_gateway
```

You can also view and manage tokens in Django Admin under **Auth Token → Tokens**.

---

## Using the Token in API Requests

Include the token in the `Authorization` header on every request:

```
Authorization: Token <your-token>
```

### Example — curl

```bash
curl -X POST http://localhost:8000/dental_ussd/dental_ussd_gw/ \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "test-123", "phoneNumber": "+1234567890", "MSG": "1", "serviceCode": "*123#"}'
```

### Example — Python `requests`

```python
import requests

response = requests.post(
    "http://localhost:8000/dental_ussd/dental_ussd_gw/",
    headers={"Authorization": "Token <your-token>"},
    json={
        "sessionId": "test-123",
        "phoneNumber": "+1234567890",
        "MSG": "1",
        "serviceCode": "*123#",
    },
)
print(response.json())
```

---

## Configuring the Vue.js USSD Simulator

The local Vue.js simulator (see [`docs/08_vue_simulator.md`](08_vue_simulator.md)) reads the token from the `VUE_APP_AUTH_TOKEN` environment variable at **build time**.

1. Generate a token for the simulator user:

   ```bash
   python manage.py drf_create_token simulator
   ```

2. Set the token in `.env` (copy from `.env.example`):

   ```
   VUE_APP_AUTH_TOKEN=<your-token>
   ```

3. Rebuild the simulator:

   ```bash
   docker compose build simulator
   ```

   Or, for the local dev server:

   ```bash
   cd /path/to/ussd-simulator
   VUE_APP_AUTH_TOKEN=<your-token> npm run serve
   ```

---

## CORS Preflight (OPTIONS) Requests

Browser-initiated cross-origin requests trigger a CORS preflight `OPTIONS` request before the actual `POST`. The `corsheaders` middleware handles preflight requests automatically before they reach the DRF authentication layer, so they are not blocked by `IsAuthenticated`. No special configuration is required.

---

## Error Responses

| Scenario | HTTP Status | Response Body |
|----------|-------------|---------------|
| No `Authorization` header | `401 Unauthorized` | `{"detail": "Authentication credentials were not provided."}` |
| Invalid or revoked token | `401 Unauthorized` | `{"detail": "Invalid token."}` |
| Valid token, insufficient permissions | `403 Forbidden` | `{"detail": "You do not have permission to perform this action."}` |

---

## Docker Deployment

When running with Docker Compose:

```bash
# Create the gateway user and generate a token
docker compose exec web python manage.py drf_create_token airtel_gateway

# Set VUE_APP_AUTH_TOKEN in .env, then rebuild the simulator
docker compose build simulator
docker compose up simulator
```
