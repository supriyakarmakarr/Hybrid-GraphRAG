FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg binary + file inspection
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl file bash \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/

EXPOSE 8000

# Default container startup without --reload for production reliability
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
