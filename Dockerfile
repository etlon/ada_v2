# --- Stage 1: Build frontend ---
FROM node:20-slim AS frontend-build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js postcss.config.js tailwind.config.js ./
COPY src/ src/
COPY public/ public/
RUN npm run build

# --- Stage 2: Python runtime ---
FROM python:3.11-slim

WORKDIR /app

# System deps for opencv, mediapipe, build123d
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers
RUN playwright install --with-deps chromium

COPY backend/ backend/
COPY --from=frontend-build /app/dist/ dist/

# Default env vars
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

WORKDIR /app/backend
CMD ["python", "server.py"]
