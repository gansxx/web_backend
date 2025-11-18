# Standalone Dockerfile for Heartbeat Detector
# This image contains ONLY the heartbeat detector service

FROM python:3.12-slim

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Set timezone
ENV TZ=Asia/Shanghai

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create non-privileged user
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/bin/bash" \
    --uid 10001 \
    appuser \
    && chown -R appuser:appuser /app

# Copy dependency files and README (needed by hatchling)
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md ./

# Switch to non-privileged user
USER appuser

# Install dependencies (creates .venv automatically)
RUN uv sync --frozen --no-dev

# Copy application files
COPY --chown=appuser:appuser heartbeat_detector.py ./
COPY --chown=appuser:appuser config.json ./

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV HEARTBEAT_CONFIG_FILE=/app/config.json
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Run the application
CMD ["python", "heartbeat_detector.py"]
