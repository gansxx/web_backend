# syntax=docker/dockerfile:1

# Multi-stage build optimized for uv package manager
# Base image with Python 3.12
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim as base

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Set timezone environment variable
ENV TZ=Asia/Shanghai

# Set working directory
WORKDIR /app

# Install system dependencies and set timezone
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create non-privileged user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/bin/bash" \
    --uid "${UID}" \
    appuser

# Change ownership of /app directory to appuser
RUN chown -R appuser:appuser /app

# Copy dependency files first for better caching
COPY --chown=appuser:appuser pyproject.toml ./
COPY --chown=appuser:appuser uv.lock* ./

# Switch to non-privileged user for dependency installation
USER appuser

# Install dependencies using uv
# This creates a virtual environment in /app/.venv
RUN uv sync --frozen --no-dev

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables for production
ENV ENVIRONMENT=production
ENV USE_GUNICORN=true
ENV BIND_ADDRESS=0.0.0.0:8001
ENV GUNICORN_WORKERS=4

# Expose ports
# 8001: Main API service
# 8002: Orchestrationer service (if running in same container)
EXPOSE 8001
EXPOSE 8002

# Health check for main API service
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application using uv
CMD ["uv", "run", "run.py", "prod"]
