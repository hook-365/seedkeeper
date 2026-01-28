FROM python:3.11-slim

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
COPY app/*.txt ./

# Copy context directory
COPY app/context/ ./context/

# Create required directories
RUN mkdir -p /app/views /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV VIEWS_DIR=/app/views

# Volumes for persistent data
VOLUME ["/app/views", "/app/data"]

CMD ["python", "seedkeeper_bot.py"]
