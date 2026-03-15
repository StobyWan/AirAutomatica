# Stage 1: Build frontend SPA
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_BASE_PATH=/dashboard
RUN npm run build

# Stage 2: Python backend + frontend dist
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
COPY alembic.ini ./
COPY alembic/ alembic/
COPY --from=frontend /app/frontend/dist ./frontend/dist

RUN pip install --no-cache-dir -e .

ENV TELEMETRY_BACKEND=mock
ENV LOCAL_LLM_PROVIDER=mock
ENV SQLITE_DB_PATH=/tmp/airautomatica.db

EXPOSE 8000

CMD ["python", "-m", "airautomatica.main"]
