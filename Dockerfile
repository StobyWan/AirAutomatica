FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/
COPY alembic.ini ./
COPY alembic/ alembic/

RUN pip install --no-cache-dir -e .

ENV TELEMETRY_BACKEND=mock
ENV LOCAL_LLM_PROVIDER=mock
ENV SQLITE_DB_PATH=/tmp/airautomatica.db

EXPOSE 8000

CMD ["python", "-m", "airautomatica.main"]
