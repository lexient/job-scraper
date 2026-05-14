FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scrape.py db.py log.py models.py seek_taxonomy.json alembic.ini ./
COPY migrations ./migrations

CMD ["python", "-u", "scrape.py"]
