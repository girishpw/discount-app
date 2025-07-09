# Stage 1: Build Tailwind CSS
FROM node:18-slim AS tailwind-builder

WORKDIR /app
COPY package.json .
RUN npm install
COPY src/tailwind.css ./src/
RUN npm run build-css

# Stage 2: Build Python Application
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy built CSS from previous stage
COPY --from=tailwind-builder /app/static/css/tailwind.css ./static/css/tailwind.css

# Copy application code
COPY . .

# Use JSON array format with environment variable
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 0 app:app"]