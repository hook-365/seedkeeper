FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/*.py ./

# Copy entrypoint scripts
COPY app/docker-entrypoint.sh .
COPY docker-entrypoint-redis.sh .
RUN chmod +x docker-entrypoint.sh docker-entrypoint-redis.sh

# Create required directories
RUN mkdir -p /app/views /app/data

# Create non-root user for security
RUN groupadd -r seedkeeper && useradd -r -g seedkeeper -u 1001 seedkeeper

# Set ownership of app directory to seedkeeper user
RUN chown -R seedkeeper:seedkeeper /app

# Set environment variables defaults
ENV PYTHONUNBUFFERED=1
ENV VIEWS_DIR=/app/views

# Switch to non-root user
USER seedkeeper

# Volumes for persistent data
VOLUME ["/app/views", "/app/data"]

# Default to Redis entrypoint, can be overridden
ENTRYPOINT ["./docker-entrypoint-redis.sh"]
CMD ["worker"]