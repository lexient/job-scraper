#!/bin/sh
set -e

name=seek-match-postgres
port=${POSTGRES_HOST_PORT:-5432}

if docker ps -a --format '{{.Names}}' | grep -q "^${name}$"; then
    docker start "$name" >/dev/null
else
    docker run -d \
        --name "$name" \
        -e POSTGRES_DB=postgres \
        -e POSTGRES_USER=seek \
        -e POSTGRES_PASSWORD=seek \
        -p ${port}:5432 \
        -v seek-match-pgdata:/var/lib/postgresql/data \
        postgres:17 >/dev/null
fi

for _ in $(seq 1 60); do
    if docker exec "$name" pg_isready -U seek -d postgres >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

python db.py
echo "postgres up on localhost:${port} (db=postgres user=seek)"
