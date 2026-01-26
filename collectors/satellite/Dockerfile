FROM python:3.12-slim

# Install cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create data and state directories
RUN mkdir -p /data/sar /data/optical /state /logs

# Copy and configure crontab
COPY crontab /etc/cron.d/satellite-collector
RUN chmod 0644 /etc/cron.d/satellite-collector \
    && crontab /etc/cron.d/satellite-collector

# Create entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set Python path
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
