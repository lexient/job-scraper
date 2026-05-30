# job-scraper

Scrapes Seek.com.au and Indeed.com.au job listings into Postgres and tracks changes over time. I host this on my homelab and have it running 24/7.

The first Seek scrape takes me under 20 minutes for 7000 jobs, with subsequent scrapes taking < 10s.

Useful for trend questions like:

- prevalence of AI in job ads over time
- how long listings stay open on average
- tech stacks gaining or losing popularity

## Running

### Everything in Docker

```
cp .env.example .env
docker compose up -d
```

The scraper loops on `SCRAPE_INTERVAL_SECONDS`.

`docker compose logs -f scraper` to tail, `docker compose down` to stop.

### Scraper locally

```
cp .env.example .env
just db          # start postgres container, run migrations
uv sync          # install deps into .venv
just scrape 5    # scrapes 5 Seek jobs
just scrape      # scrapes all Seek jobs
just scrape-indeed   # scrapes Indeed
```

`docker compose up` scrapes Seek by default. Set by `SCRAPE_SOURCE` in the .env

Indeed sits behind Cloudflare, so it drives a real browser (Chromium via nodriver)
instead of the JSON API. The image bundles Chromium and runs it under xvfb. Locally
`just scrape-indeed` needs Chrome or Chromium installed.

## Common commands

`just` shows everything available.

- `just db-shell` open a psql shell against the local db
- `just db-reset` nuke and recreate the db
- `just migration "add salary column"` autogenerate an Alembic migration
- `just migrate` apply pending migrations
- `just lint` ruff fix and format
- `just check` ruff check without writing

## Config

See `.env.example`.

## Rate limits

- Set `CONCURRENCY` lower.
- Use a residential IP address (I had mixed results hosting from a datacentre).

## Requirements

[uv](https://docs.astral.sh/uv/), [just](https://github.com/casey/just), Docker.
