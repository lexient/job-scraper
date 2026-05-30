default:
    @just --list

up:
    docker compose up -d

down:
    docker compose down

logs:
    docker compose logs -f scraper

db:
    docker compose up -d --wait postgres
    uv run alembic upgrade head

db-reset:
    docker compose down -v
    docker compose up -d --wait postgres
    uv run alembic upgrade head

db-shell:
    docker exec -it job-scraper-postgres psql -U seek postgres

scrape limit="99999":
    uv run python -m job_scraper.seek {{limit}}

scrape-indeed limit="99999":
    uv run python -m job_scraper.indeed {{limit}}

migrate:
    uv run alembic upgrade head

migration msg:
    uv run alembic revision --autogenerate -m "{{msg}}"

lint:
    uv run ruff check . --fix
    uv run ruff format .

check:
    uv run ruff check .
    uv run ruff format --check .
