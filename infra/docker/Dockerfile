FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALERTPILOT_ENV=production \
    ALERTPILOT_DB_PATH=/app/data/alertpilot.db

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY alertpilot /app/alertpilot
COPY static /app/static
COPY scripts /app/scripts
COPY dvc.yaml params.yaml /app/
RUN mkdir -p /app/data /app/logs
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -f http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "alertpilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
