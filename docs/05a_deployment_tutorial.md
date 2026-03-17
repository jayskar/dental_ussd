# Deployment Tutorial

> **Audience**: Learners and developers deploying for the first time. Every command is explained.

---

## 1. Introduction

In this guide we'll take the Dental USSD app from your local machine and deploy it so a real USSD gateway can reach it. We'll cover three paths:

- **Option A**: Local development (recap — for testing only)
- **Option B**: VPS with Nginx + Gunicorn (manual Ubuntu deploy)
- **Option C**: Docker (the easiest path for most people)

By the end you'll have a running server, a database, and Redis — the three things the app needs to work.

---

## 2. Option A: Local Development

Already covered in the Quick Start guide. Short recap:

```bash
git clone https://github.com/jayskar/dental_ussd.git
cd dental_ussd
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DEBUG=True, fill in SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
redis-server &
python manage.py runserver
```

Your app will be available at `http://127.0.0.1:8000/`. This is **not** accessible from the internet. Use Option B or C for that.

---

## 3. Option B: VPS with Nginx + Gunicorn (Manual)

This is the traditional approach. You rent a server, install everything by hand, and manage it yourself. It gives you full control but requires more steps.

### 3.1 Provision an Ubuntu 22.04 VPS

Use any cloud provider (DigitalOcean, Hetzner, Linode, AWS EC2, etc.). Choose Ubuntu 22.04 LTS. After creating the server, SSH into it:

```bash
ssh root@YOUR_SERVER_IP
```

### 3.2 Install System Packages

```bash
# Update package list
apt update && apt upgrade -y

# Install Python 3.12, pip, Redis, Nginx, and git
apt install -y python3.12 python3.12-venv python3-pip redis-server nginx git

# Verify Redis is running
redis-cli ping   # should print: PONG
```

### 3.3 Create an App User

It's best practice to run the app as a non-root user:

```bash
adduser appuser          # follow prompts
usermod -aG www-data appuser
su - appuser
```

### 3.4 Clone the Repository and Set Up venv

```bash
cd /home/appuser
git clone https://github.com/jayskar/dental_ussd.git
cd dental_ussd

python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3.5 Configure `.env` for Production

```bash
cp .env.example .env
nano .env
```

Set these values for production:

```ini
SECRET_KEY=your-long-random-secret-key-here-at-least-50-chars
DEBUG=False
ALLOWED_HOSTS=your-domain.com,YOUR_SERVER_IP
REDIS_URL=redis://127.0.0.1:6379/0
CORS_ALLOWED_ORIGINS=https://your-domain.com
ANON_THROTTLE_RATE=60/minute
```

> **Generating a secure SECRET_KEY:**
> ```bash
> python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

### 3.6 Run Migrations and Collect Static Files

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

`collectstatic` gathers all static files (Django admin CSS, JS) into `staticfiles/`. WhiteNoise will serve them from there.

### 3.7 Test Gunicorn Manually

Before setting up `systemd`, confirm Gunicorn starts correctly:

```bash
gunicorn dental_app.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

If you see `Listening at: http://0.0.0.0:8000`, press `Ctrl+C` and continue.

### 3.8 Create a `systemd` Service for Gunicorn

`systemd` will ensure Gunicorn starts automatically and restarts on failure.

```bash
# Switch back to root to create the service file
exit   # exit appuser shell
nano /etc/systemd/system/dental_ussd.service
```

Paste this content (adjust paths as needed):

```ini
[Unit]
Description=Dental USSD Gunicorn Daemon
After=network.target

[Service]
User=appuser
Group=www-data
WorkingDirectory=/home/appuser/dental_ussd
EnvironmentFile=/home/appuser/dental_ussd/.env
ExecStart=/home/appuser/dental_ussd/venv/bin/gunicorn \
          dental_app.wsgi:application \
          --bind unix:/run/dental_ussd.sock \
          --workers 3 \
          --timeout 120 \
          --access-logfile /var/log/dental_ussd/access.log \
          --error-logfile /var/log/dental_ussd/error.log
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
mkdir -p /var/log/dental_ussd
chown appuser:www-data /var/log/dental_ussd
systemctl daemon-reload
systemctl enable dental_ussd
systemctl start dental_ussd
systemctl status dental_ussd   # should show "active (running)"
```

### 3.9 Configure Nginx as a Reverse Proxy

Nginx will sit in front of Gunicorn, handle SSL, and serve as the public-facing web server.

```bash
nano /etc/nginx/sites-available/dental_ussd
```

```nginx
server {
    listen 80;
    server_name your-domain.com YOUR_SERVER_IP;

    location /static/ {
        alias /home/appuser/dental_ussd/staticfiles/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/dental_ussd.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable the site:

```bash
ln -s /etc/nginx/sites-available/dental_ussd /etc/nginx/sites-enabled/
nginx -t          # test configuration — should print "syntax is ok"
systemctl restart nginx
```

### 3.10 Test the Setup

```bash
curl http://YOUR_SERVER_IP/dental_ussd/dental_ussd_gw/ \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"test-1","phoneNumber":"+67570001111","MSG":"","serviceCode":"*123#"}'
```

You should get a USSD welcome response. 🎉

---

## 4. Option C: Docker (Beginner-Friendly)

Docker packages the app and all its dependencies into containers that run identically on any machine. You don't need to install Python or Redis manually — Docker handles it all.

### 4.1 What is Docker and Why We Use It

Docker lets you run applications in isolated containers. `docker compose` lets you run multiple containers (our Django app + Redis + the Vue simulator) together with a single command. It's the easiest way to get a consistent, reproducible environment.

### 4.2 Install Docker and Docker Compose

**Linux (Ubuntu):**

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER   # add yourself to the docker group
newgrp docker               # activate the new group

# Verify
docker --version
docker compose version
```

**macOS**: Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).  
**Windows**: Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (requires WSL2).

### 4.3 The `Dockerfile` Line by Line

```dockerfile
# syntax=docker/dockerfile:1

# Build stage: installs dependencies in a throwaway container
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y git   # git needed for pip install from GitHub
WORKDIR /app
RUN python -m venv /opt/venv                    # isolated virtual env
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt             # install all Python deps
# Patch an older dependency for Python 3.12 compatibility

# Runtime stage: lean final image, copies only the installed packages
FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y git
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser  # non-root user
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv         # copy installed packages
ENV PATH="/opt/venv/bin:$PATH"
COPY . .                                         # copy app source
RUN chmod +x docker-entrypoint.sh
RUN mkdir -p /app/data /app/staticfiles && chown -R appuser:appgroup /app
USER appuser                                     # run as non-root
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]            # runs migrate, collectstatic, gunicorn
```

The multi-stage build keeps the final image small — the `builder` stage (with `git` and build tools) is discarded.

### 4.4 The `docker-compose.yml` Line by Line

```yaml
services:
  redis:                          # Redis session/cache store
    image: redis:7-alpine         # official Redis 7, tiny Alpine Linux base
    restart: unless-stopped       # restart on failure, stop only on explicit stop
    volumes:
      - redis_data:/data          # persist Redis data across restarts
    healthcheck:                  # wait for Redis to be ready before starting web

  web:                            # Django + Gunicorn
    build:
      context: .
      target: runtime             # use the "runtime" stage of the Dockerfile
    ports:
      - "${WEB_PORT:-8000}:8000"  # host port 8000 → container port 8000
    env_file: .env                # load .env file into the container
    environment:
      REDIS_URL: redis://redis:6379/0  # override to use the compose Redis service
      DB_DIR: /app/data                # SQLite file lives on the volume
    volumes:
      - db_data:/app/data         # persist SQLite database
      - static_files:/app/staticfiles
    depends_on:
      redis:
        condition: service_healthy  # wait until Redis passes its health check

  simulator:                      # Vue.js USSD simulator (dev/testing only)
    build:
      dockerfile: Dockerfile.simulator
    ports:
      - "${SIMULATOR_PORT:-8081}:8081"
    depends_on:
      - web
```

### 4.5 Running with `docker compose up`

```bash
cd dental_ussd
cp .env.example .env   # configure your .env
docker compose up      # builds images and starts all services
```

On first run, Docker will:
1. Pull `redis:7-alpine`
2. Build the `web` image (installing all Python dependencies)
3. Build the `simulator` image
4. Run `docker-entrypoint.sh` (migrate → collectstatic → gunicorn)

Once you see `Listening at: http://0.0.0.0:8000`, your app is ready.

To run in the background (detached mode):

```bash
docker compose up -d
```

### 4.6 Viewing Logs

```bash
docker compose logs -f web        # follow Django/Gunicorn logs
docker compose logs -f redis      # Redis logs
docker compose logs               # all services
```

### 4.7 Common Beginner Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Forgot to copy `.env.example` to `.env` | Container exits with `ImproperlyConfigured` | `cp .env.example .env` |
| Docker Desktop not running | `Cannot connect to the Docker daemon` | Open Docker Desktop |
| Port 8000 already in use | `bind: address already in use` | Stop the other process or change `WEB_PORT=8001` in `.env` |
| Forgot `docker compose build` after changing requirements | Old image used | `docker compose build web` |
| Edited code but container uses old version | Changes not reflected | `docker compose up --build` |

---

## 5. Environment Variables Reference

| Variable | Default | Required | Description |
|---|---|---|---|
| `SECRET_KEY` | `django-insecure-change-me-in-production` | ✅ (prod) | Django secret key. Must be set to a unique value in production. |
| `DEBUG` | `False` | No | Enable Django debug mode. **Never `True` in production.** |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | ✅ (prod) | Comma-separated allowed hostnames. |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | No | Redis connection URL. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:8081,...` | No | Comma-separated CORS allowed origins. |
| `ANON_THROTTLE_RATE` | `60/minute` | No | DRF rate limit for anonymous requests. |
| `DB_DIR` | project root | No | Directory where `db.sqlite3` is created. |
| `WEB_PORT` | `8000` | No | Host port for the Django container. |
| `GUNICORN_WORKERS` | `3` | No | Number of Gunicorn worker processes. |
| `GUNICORN_TIMEOUT` | `120` | No | Gunicorn worker timeout in seconds. |
| `VUE_APP_AUTH_TOKEN` | _(empty)_ | No | DRF token baked into the Vue simulator build. |
| `SIMULATOR_PORT` | `8081` | No | Host port for the simulator container. |

---

← [Previous: Journey Engine](04_journey_engine.md) | [Back to README](../README.md) | [Next: Production Deployment →](05b_deployment_production.md)
