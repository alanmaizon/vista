FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/react/package.json frontend/react/package-lock.json ./
RUN npm ci
COPY frontend/react ./
COPY logo.svg public/logo.svg
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required by asyncpg and firebase
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements-music.txt ./
RUN pip install --no-cache-dir -r requirements-music.txt

COPY backend/app ./app
COPY --from=frontend /frontend/dist ./frontend-dist

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
