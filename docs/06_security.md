# Security Guide

> **Codebase reference**: `dental_app/settings.py`, `dental_ussd/views.py`.

---

## 1. Security Model Overview

The Dental USSD app's security model differs significantly from a typical browser-facing REST API:

- **No browser clients** — USSD gateways are server-to-server HTTP clients. There are no cookies, no browser sessions, and no human-readable tokens to protect.
- **Phone number as identity** — The caller's phone number is verified by the telco before the request reaches Django. It is the authoritative patient identifier.
- **No auth tokens from gateways** — USSD gateways do not send Bearer tokens or API keys by default. Authentication happens at the network layer (IP allowlisting), not the HTTP layer.

---

## 2. USSD Endpoint Security

### Token Authentication

```python
class DentalAppUssdGateway(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]
```

Every caller must authenticate with a DRF token. A Django user account is created for each gateway or simulator, and a token is generated with `python manage.py drf_create_token <username>`. The caller sends:

```
Authorization: Token <token>
```

Requests without a valid token receive `401 Unauthorized`. See [docs/authentication.md](authentication.md) for setup instructions.

### Why `csrf_exempt` Is Correct

USSD gateways POST without a CSRF token. There is no browser, no cookie, and no CSRF attack vector. The decorator is correct here.

### IP Allowlisting (Recommended)

Add a middleware or Nginx rule to restrict `POST /dental_ussd/dental_ussd_gw/` to the gateway's known IP range:

**Nginx approach:**

```nginx
location /dental_ussd/ {
    allow 196.201.216.0/23;   # Africa's Talking gateway IPs (example)
    deny all;
    proxy_pass http://django_app;
}
```

**Django middleware approach:**

```python
# dental_ussd/middleware.py
from django.http import HttpResponseForbidden

ALLOWED_GATEWAY_IPS = ['196.201.216.1', '196.201.216.2']

class GatewayIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/dental_ussd/'):
            ip = request.META.get('REMOTE_ADDR', '')
            if ip not in ALLOWED_GATEWAY_IPS:
                return HttpResponseForbidden('Forbidden')
        return self.get_response(request)
```

---

## 3. Environment Variables

### `SECRET_KEY`

Django uses `SECRET_KEY` for signing cookies, sessions, CSRF tokens, and password reset links. A compromised key can lead to forged sessions and data leakage.

- **Never commit** the production `SECRET_KEY` to version control.
- Generate a new key for every environment:
  ```bash
  python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```
- **Rotate** the key if it is ever exposed. Rotating the key invalidates all existing sessions and tokens.

The app enforces this at startup:

```python
if not DEBUG and SECRET_KEY == _DEFAULT_SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set to a secure value ...")
```

### `DEBUG=False` in Production

`DEBUG=True` exposes:
- Full stack traces to end users
- All environment variables and settings
- The interactive Django error page

Always set `DEBUG=False` in production.

### `ALLOWED_HOSTS`

Set `ALLOWED_HOSTS` to only your actual domain(s) and server IP(s). An empty or wildcard `ALLOWED_HOSTS` with `DEBUG=False` will raise a `DisallowedHost` error.

```ini
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
```

---

## 4. CORS Configuration

### What `CORS_ALLOWED_ORIGINS` Does

`django-cors-headers` adds `Access-Control-Allow-Origin` headers to responses, controlling which browser origins can call the API. This matters only for browser-based clients (e.g. the Vue simulator).

### Development Configuration

```ini
CORS_ALLOWED_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
```

This allows the Vue simulator (running at `localhost:8081`) to POST to the Django API from the browser.

### Production Configuration

In production, the Vue simulator should not be running. Set `CORS_ALLOWED_ORIGINS` to only your legitimate frontend domain:

```ini
CORS_ALLOWED_ORIGINS=https://your-domain.com
```

Or, if the USSD endpoint is called only by the gateway (server-to-server), CORS headers are irrelevant and you can leave the setting restrictive or empty.

---

## 5. Phone Number Privacy

Phone numbers are stored as the `Patient.mobile_number` field and used as session identifiers. They are considered PII (personally identifiable information).

**Recommendations:**

- **Mask in logs**: Avoid logging full phone numbers. Log only the last 4 digits where needed for debugging:
  ```python
  masked = f"****{phone_number[-4:]}"
  logger.info("Processing request", phone=masked)
  ```
- **Do not log full phone numbers** in `structlog` calls — check all `logger.info/error` calls in `utils.py`.
- **Database**: Consider encrypting `mobile_number` at rest using `django-encrypted-fields` for high-compliance deployments.
- **Admin**: Restrict admin access (see Section 7) to prevent unauthorised viewing of patient data.

---

## 6. Redis Session Security

### JSON Serialiser (Safer Than Pickle)

The app uses Django's JSON serialiser for session data:

```python
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'
```

The default `PickleSerializer` is vulnerable to arbitrary code execution if an attacker can write to Redis. JSON is safe because it cannot encode executable Python objects.

### Redis Authentication

Set a Redis password in production:

```
# /etc/redis/redis.conf
requirepass your-strong-redis-password
```

Update `REDIS_URL`:

```ini
REDIS_URL=redis://:your-strong-redis-password@127.0.0.1:6379/0
```

### Redis Network Exposure

**Never** bind Redis to `0.0.0.0` in production. It must only be accessible from `localhost` (VPS) or the Docker internal network:

```
# /etc/redis/redis.conf
bind 127.0.0.1
```

---

## 7. Admin Panel Security

The Django Admin at `/admin/` has full access to all patient, appointment, and clinic data.

### Change the Admin URL

Exposing `/admin/` on a well-known URL invites automated attacks. Rename it:

```python
# dental_app/urls.py
urlpatterns = [
    path('my-secret-admin-path/', admin.site.urls),
    ...
]
```

### Strong Passwords

Enforce strong passwords for all Django Admin users. The app already configures Django's built-in password validators in `settings.py`.

### Restrict Admin to VPN or IP

In Nginx, restrict the admin path to your office IP or VPN:

```nginx
location /admin/ {
    allow 203.0.113.0/24;   # your office IP range
    deny all;
    proxy_pass http://django_app;
}
```

---

## 8. Rate Limiting

### Current State

The app configures DRF's `AnonRateThrottle` at 60 requests/minute per IP:

```python
"DEFAULT_THROTTLE_RATES": {
    "anon": config('ANON_THROTTLE_RATE', default='60/minute'),
}
```

This provides basic protection against rapid-fire requests from a single IP.

### Recommendations

For more robust rate limiting:

- **Nginx rate limiting**: Handles rate limiting before requests reach Django, more efficient.
  ```nginx
  limit_req_zone $binary_remote_addr zone=ussd:10m rate=10r/s;
  location /dental_ussd/ {
      limit_req zone=ussd burst=20 nodelay;
  }
  ```
- **`django-ratelimit`**: More granular, can rate-limit per phone number instead of per IP.

---

## 9. HTTPS

Always use HTTPS in production. Without HTTPS:

- Phone numbers (PII) are transmitted in plaintext
- Session tokens can be intercepted
- The `Strict-Transport-Security` header cannot be served

### HSTS Header

After obtaining an SSL certificate, add HSTS to Nginx:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

This tells browsers (and HTTP clients) to always use HTTPS for your domain for one year.

Also add to Django settings for the `django.middleware.security.SecurityMiddleware`:

```python
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True  # redirect HTTP to HTTPS
```

---

## 10. Dependency Security

### Pinned Versions

All dependencies in `requirements.txt` are pinned to exact versions. This prevents surprise upgrades that could introduce vulnerabilities. However, it also means security fixes are not automatically applied.

### Auditing Dependencies

Run `pip audit` periodically to check for known vulnerabilities:

```bash
pip install pip-audit
pip-audit
```

Or use GitHub's Dependabot (free for public repos) to receive automated pull requests when vulnerabilities are found in pinned dependencies.

---

← [Previous: Production Deployment](05b_deployment_production.md) | [Back to README](../README.md) | [Next: Known Bugs →](07_known_bugs.md)
