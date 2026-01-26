FROM python:3.12-slim

# Install cron
RUN apt-get update && \
    apt-get install -y --no-install-recommends cron && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create directories for data and logs
RUN mkdir -p /data /logs

# Set up crontab for hourly execution
# Run at minute 0 of every hour
RUN echo "0 * * * * cd /app/src && /usr/local/bin/python fetch.py >> /var/log/cron.log 2>&1" > /etc/cron.d/weather-collector && \
    chmod 0644 /etc/cron.d/weather-collector && \
    crontab /etc/cron.d/weather-collector

# Create log file for cron
RUN touch /var/log/cron.log

# Set environment variables
ENV DATA_DIR=/data
ENV LOG_DIR=/logs
ENV PYTHONUNBUFFERED=1

# Run initial collection on startup, then start cron
CMD cd /app/src && python fetch.py && cron && tail -f /var/log/cron.log
