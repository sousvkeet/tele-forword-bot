# Telegram Auto Forwarder - Production Dockerfile
FROM python:3.11-slim

# Set maintainer info
LABEL maintainer="Telegram Auto Forwarder"
LABEL description="Production-ready Telegram message forwarding bot with web dashboard"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV DEBIAN_FRONTEND=noninteractive

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libffi-dev \
        libssl-dev \
        curl \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/static /app/templates \
    && chown -R appuser:appuser /app

# Create volume mount points
VOLUME ["/app/data", "/app/logs"]

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5001/api/status || exit 1

# Switch to non-root user
USER appuser

# Start command
CMD ["python", "app.py"]
