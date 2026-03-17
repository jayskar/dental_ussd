# Deployment — Production Reference

> **Audience**: Production developers. Concise reference format.

---

## 1. Environment Variables Reference

| Variable | Type | Default | Required | Description |
|---|---|---|---|---|
| `SECRET_KEY` | string | `django-insecure-change-me-in-production` | ✅ prod | Django secret key — must be long, random, unique in production. |
| `DEBUG` | bool | `False` | No | Debug mode. Must be `False` in production. |
| `ALLOWED_HOSTS` | CSV | `localhost,127.0.0.1` | ✅ prod | Allowed hostnames/IPs. |
| `REDIS_URL` | string | `redis://127.0.0.1:6379/0` | No | Redis connection URL (supports `rediss://` for TLS). |
| `CORS_ALLOWED_ORIGINS` | CSV | `http://localhost:8081,...` | No | CORS allowed origins. Set to your frontend domain in production. |
| `ANON_THROTTLE_RATE` | string | `60/minute` | No | DRF anonymous throttle rate. |
| `DB_DIR` | path | project root | No | Directory for `db.sqlite3`. Override in Docker to a volume path. |
| `WEB_PORT` | int | `8000` | No | Docker host port for the web service. |
| `GUNICORN_WORKERS` | int | `3` | No | Number of Gunicorn worker processes. |
| `GUNICORN_TIMEOUT` | int | `120` | No | Gunicorn worker timeout (seconds). |
| `VUE_APP_AUTH_TOKEN` | string | _(empty)_ | No | DRF auth token for the Vue simulator build. |
| `SIMULATOR_PORT` | int | `8081` | No | Docker host port for the simulator service. |

---

## 2. VPS + Nginx + Gunicorn (Production-Hardened)

### Nginx Configuration

```nginx
# /etc/nginx/sites-available/dental_ussd

upstream django_app {
    server unix:/run/dental_ussd.sock fail_timeout=0;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy no-referrer-when-downgrade always;

    client_max_body_size 4M;

    location /static/ {
        alias /home/appuser/dental_ussd/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://django_app;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }
}
```

### `gunicorn.conf.py`

```python
# /home/appuser/dental_ussd/gunicorn.conf.py

bind = "unix:/run/dental_ussd.sock"
workers = 3           # formula: (2 × CPU cores) + 1
worker_class = "sync"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "/var/log/dental_ussd/access.log"
errorlog = "/var/log/dental_ussd/error.log"
loglevel = "info"
```

Start with:

```bash
gunicorn dental_app.wsgi:application -c gunicorn.conf.py
```

### `systemd` Service Unit

```ini
# /etc/systemd/system/dental_ussd.service

[Unit]
Description=Dental USSD Gunicorn Daemon
After=network.target redis.service

[Service]
User=appuser
Group=www-data
WorkingDirectory=/home/appuser/dental_ussd
EnvironmentFile=/home/appuser/dental_ussd/.env
ExecStart=/home/appuser/dental_ussd/venv/bin/gunicorn \
          dental_app.wsgi:application \
          -c /home/appuser/dental_ussd/gunicorn.conf.py
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5s
RuntimeDirectory=dental_ussd
RuntimeDirectoryMode=0755

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now dental_ussd
```

### SSL with Let's Encrypt

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
# Certbot auto-modifies the Nginx config and sets up auto-renewal
```

### `collectstatic` and WhiteNoise

`collectstatic` must be run before starting Gunicorn (the entrypoint script does this automatically in Docker):

```bash
python manage.py collectstatic --noinput
```

WhiteNoise is configured in `settings.py` via `STORAGES`:

```python
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

This adds content-hash fingerprinting and gzip/brotli compression to static assets. The `WhiteNoiseMiddleware` in `MIDDLEWARE` serves them directly from Gunicorn without hitting Nginx.

---

## 3. Docker Production Deployment

### `docker-compose.yml` with Nginx

For production, add an Nginx service to the compose file:

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --requirepass "${REDIS_PASSWORD}"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    build:
      context: .
      target: runtime
    restart: unless-stopped
    env_file: .env
    environment:
      REDIS_URL: "redis://:${REDIS_PASSWORD}@redis:6379/0"
      DB_DIR: /app/data
    volumes:
      - db_data:/app/data
      - static_files:/app/staticfiles
    depends_on:
      redis:
        condition: service_healthy
    expose:
      - "8000"

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - static_files:/app/staticfiles:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - web

volumes:
  redis_data:
  db_data:
  static_files:
```

### Build and Run

```bash
docker compose pull
docker compose build
docker compose up -d
```

### Health Checks

```bash
docker compose ps          # shows health status of each service
docker compose exec web python manage.py check --deploy
```

### Persisting Data with Volumes

| Volume | Contains |
|---|---|
| `db_data` | SQLite database (`db.sqlite3`) |
| `redis_data` | Redis persistence (RDB snapshot) |
| `static_files` | Collected static assets |

To back up the database:

```bash
docker compose exec web cp /app/data/db.sqlite3 /app/data/db.sqlite3.bak
docker cp $(docker compose ps -q web):/app/data/db.sqlite3.bak ./db_backup.sqlite3
```

---

## 4. Database

### SQLite (Development Only)

SQLite is appropriate for development and very low-traffic deployments. Limitations:

- No concurrent write support — multiple Gunicorn workers can cause write contention
- Not suitable for more than ~100 concurrent users
- No network access — cannot be shared between multiple app instances

### Migrating to PostgreSQL

1. Install `psycopg2-binary`:

```bash
pip install psycopg2-binary
echo "psycopg2-binary==2.9.9" >> requirements.txt
```

2. Update `settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='dental_ussd'),
        'USER': config('DB_USER', default='dental_user'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}
```

3. Add to `.env`:

```ini
DB_NAME=dental_ussd
DB_USER=dental_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432
```

4. Run migrations against the new database:

```bash
python manage.py migrate
```

---

## 5. Redis Configuration

### Connection Pooling

`django-redis` manages a connection pool by default. To tune it:

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
            },
        }
    }
}
```

### Persistence

By default, Redis uses RDB snapshotting. For session data durability, enable AOF in `redis.conf`:

```
appendonly yes
appendfsync everysec
```

### Network Exposure

**Never** expose the Redis port (`6379`) to the public internet. In production:

- Bind Redis to `127.0.0.1` (VPS) or use Docker's internal network (container-only)
- Set a Redis password: `requirepass your-redis-password`
- Update `REDIS_URL`: `redis://:your-redis-password@127.0.0.1:6379/0`

---

## 6. Process Management

### Gunicorn Workers Formula

```
workers = (2 × CPU_CORES) + 1
```

For a 2-core VPS: `workers = 5`. For a single-core: `workers = 3`.

USSD requests are short-lived (< 1 second each) with I/O wait (database, Redis), so the sync worker class is appropriate.

### Timeouts

- `--timeout 120` — worker killed after 120 seconds of inactivity. USSD requests are fast; this is a safety net.
- `--keepalive 5` — keep connections open for 5 seconds between requests.

---

## 7. Monitoring and Logging

### structlog Output

The app uses `structlog` for structured logging. In development, logs are human-readable. In production, configure JSON output for log aggregation:

```python
# settings.py — add to configure structlog for production
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
```

### Log Aggregation

Suggested tools:

| Tool | How to use |
|---|---|
| **Loki + Grafana** | Collect Docker/systemd logs; free and self-hosted |
| **Datadog** | Agent-based; commercial |
| **CloudWatch** (AWS) | Native on EC2; paid per ingestion |
| **Papertrail** | Syslog forwarding; simple setup |

---

← [Previous: Deployment Tutorial](05a_deployment_tutorial.md) | [Back to README](../README.md) | [Next: Security →](06_security.md)
