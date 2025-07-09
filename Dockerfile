# Dockerfile for Discount App - Updated: 2025-07-08 12:20 UTC
FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with explicit gunicorn
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn==21.2.0

# Verify gunicorn is installed and show PATH
RUN which gunicorn && gunicorn --version && echo "PATH: $PATH"

# Copy application code
COPY . .

EXPOSE 5000

# Use full path to gunicorn as backup
CMD exec /usr/local/bin/gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 8 --timeout 0 app:app
