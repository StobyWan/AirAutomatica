FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

ENV TELEMETRY_BACKEND=mock
ENV AI_MODE=mock
ENV SQLITE_DB_PATH=/tmp/airautomatica.db

EXPOSE 8000

CMD ["python", "-m", "airautomatica.main"]
