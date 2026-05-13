# job-scraper

Scrapes Seek.com.au job listings into Postgres and tracks changes over time.

By default, it only tracks ICT listings, you can change `classification_id` in `scrape.py` to any top-level ID from `seek_taxonomy.json`.

## Run everything in docker

```
cp .env.example .env
docker compose up -d
```

Postgres on `localhost:${POSTGRES_HOST_PORT}` (default 5432), scraper loops every `SCRAPE_INTERVAL_SECONDS`.

## Run scraper locally against dockerised postgres

```
cp .env.example .env
./postgres.sh        # starts postgres container, runs schema init
pip install -r requirements.txt
python scrape.py 100 # arg is max jobs per run, defaults to 5
```

## Config

See `.env.example`. Set `DATABASE_URL` to point at a remote DB. Set `CONCURRENCY` lower if you run into rate limits.
