# Add NodeJS and build Tailwind
FROM node:18-slim as tailwind-builder

WORKDIR /app
COPY package.json .
RUN npm install
COPY src/tailwind.css ./src/
RUN npm run build-css

# Python build
FROM python:3.9-slim

WORKDIR /app
COPY --from=tailwind-builder /app/static/css/tailwind.css ./static/css/tailwind.css

# Rest of existing Dockerfile...
COPY . .