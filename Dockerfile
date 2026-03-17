# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build stage: install Python dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# System packages needed to install some Python dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies into a virtual-env so we can copy only what we need
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    # Patch PyConfigure==0.5.9 for Python 3.12 compatibility.
    # inspect.getargspec and collections.MutableMapping/Mapping were removed in 3.12.
    # This is a targeted fix for the pinned version used by ussd_airflow_engine.
    && python - <<'EOF'
import re, pathlib
p = pathlib.Path('/opt/venv/lib/python3.12/site-packages/configure.py')
src = p.read_text()
src = src.replace('from inspect import getargspec', 'from inspect import getfullargspec as getargspec')
src = re.sub(r'from collections import (MutableMapping, Mapping|Mapping, MutableMapping)',
             'from collections.abc import MutableMapping, Mapping', src)
p.write_text(src)
EOF

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# System packages required at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the application
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY . .

# Ensure the entrypoint is executable
RUN chmod +x docker-entrypoint.sh

# Create the directory for SQLite data and static files; set ownership
RUN mkdir -p /app/data /app/staticfiles \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
