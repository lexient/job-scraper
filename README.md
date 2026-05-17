# job-scraper

Scrapes Seek.com.au job listings into Postgres and tracks changes over time.

By default, it only tracks ICT listings, you can change `classification_id` in `scrape.py` to any top-level ID from `seek_taxonomy.json`.

## Run everything in docker

```
cp .env.example .env
docker compose up -d
```

Postgres on `localhost:${POSTGRES_HOST_PORT}` (default 5432), scraper loops every `SCRAPE_INTERVAL_SECONDS`.

`docker compose logs -f scraper` to tail, `docker compose down` to stop.

## Run scraper locally against dockerised postgres

```
cp .env.example .env
just db              # start postgres container, run migrations
uv sync              # install deps into .venv
just scrape 9999      # arg is max jobs per run, defaults to 5
```

## Common commands

`just` shows everything available.

- `just db-shell` open a psql shell against the local db
- `just db-reset` nuke and recreate the db
- `just migration "add salary column"` autogenerate an Alembic migration
- `just migrate` apply pending migrations
- `just lint` ruff fix and format
- `just check` ruff check without writing

## Config

See `.env.example`. Set `DATABASE_URL` to point at a remote DB. Set `CONCURRENCY` lower if you run into rate limits.

## Requirements

[uv](https://docs.astral.sh/uv/), [just](https://github.com/casey/just), Docker.
