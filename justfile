default:
    @just --list

up:
    docker compose up -d

down:
    docker compose down

logs:
    docker compose logs -f scraper

db:
    ./postgres.sh

db-reset:
    docker compose down -v
    ./postgres.sh

db-shell:
    docker exec -it job-scraper-postgres psql -U seek postgres

scrape limit="5":
    uv run python scrape.py {{limit}}

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
