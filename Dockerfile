FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl and libpq-dev are useful for healthchecks and postgres utilities)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt /app/requirements-api.txt

RUN pip install --no-cache-dir -r requirements-api.txt

COPY api /app/api
COPY src /app/src
COPY sql /app/sql

ENV PYTHONPATH=/app

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
