#!/usr/bin/env python3

import hashlib
import json
import os

import psycopg
from psycopg.types.json import Jsonb
from dotenv import load_dotenv


load_dotenv(override=True)

_port = os.environ.get("POSTGRES_HOST_PORT", "5432")
database_url = os.environ.get("DATABASE_URL", f"postgresql://seek:seek@localhost:{_port}/postgres")


schema = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT,
    teaser TEXT,
    company TEXT,
    advertiser_id TEXT,
    classification TEXT,
    subclassification TEXT,
    location TEXT,
    work_type TEXT,
    work_arrangement TEXT,
    salary_label TEXT,
    listing_date TEXT,
    url TEXT,
    role_id TEXT,
    display_type TEXT,
    is_featured BOOLEAN,
    bullet_points TEXT[],
    tags TEXT[],
    raw_json JSONB,
    raw_html TEXT,
    html_hash TEXT,
    html_fetched_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,
    delisted_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    content_hash TEXT,
    content_changed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS job_details (
    id TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    location TEXT,
    work_type TEXT,
    salary TEXT,
    rating TEXT,
    classifications TEXT[],
    url TEXT,
    markdown TEXT,
    source_hash TEXT,
    cleaned_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_history (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ DEFAULT NOW(),
    event TEXT NOT NULL,
    content_hash TEXT,
    html_hash TEXT,
    raw_json JSONB,
    markdown TEXT
);

CREATE INDEX IF NOT EXISTS job_history_job_id_idx ON job_history (job_id, observed_at);
CREATE INDEX IF NOT EXISTS job_history_event_idx ON job_history (event, observed_at);
"""


def connect():
    return psycopg.connect(database_url)


def init():
    conn = connect()
    conn.execute(schema)
    conn.commit()
    conn.close()


# excludes tags/bulletPoints which flap
_content_keys = [
    "title", "teaser", "companyName", "salaryLabel",
    "workArrangements", "workTypes", "classifications",
    "locations", "listingDate",
]


def content_hash(job):
    serial = json.dumps({k: job.get(k) for k in _content_keys}, sort_keys=True, default=str)
    return hashlib.sha256(serial.encode()).hexdigest()


def log_history(conn, job_id, event, content_hash=None, html_hash=None, raw_json=None, markdown=None):
    conn.execute(
        """
        INSERT INTO job_history (job_id, event, content_hash, html_hash, raw_json, markdown)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            job_id,
            event,
            content_hash,
            html_hash,
            Jsonb(raw_json) if raw_json is not None else None,
            markdown,
        ),
    )


def upsert_job(conn, job):
    job_id = str(job["id"])
    classif = (job.get("classifications") or [{}])[0]
    location = (job.get("locations") or [{}])[0].get("label")
    work_type = (job.get("workTypes") or [None])[0]
    work_arrangement = (job.get("workArrangements") or {}).get("displayText")
    tags = [t.get("type") for t in (job.get("tags") or []) if t.get("type")]
    bullet_points = job.get("bulletPoints") or []
    chash = content_hash(job)

    prev = conn.execute(
        "SELECT content_hash, delisted_at FROM jobs WHERE id = %s",
        (job_id,),
    ).fetchone()
    is_new = prev is None
    prev_hash = prev[0] if prev else None
    was_delisted = bool(prev and prev[1] is not None)

    conn.execute("""
        INSERT INTO jobs
        (id, title, teaser, company, advertiser_id, classification, subclassification,
         location, work_type, work_arrangement, salary_label, listing_date, url,
         role_id, display_type, is_featured, bullet_points, tags, raw_json,
         content_hash, content_changed_at, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            teaser = EXCLUDED.teaser,
            company = EXCLUDED.company,
            advertiser_id = EXCLUDED.advertiser_id,
            classification = EXCLUDED.classification,
            subclassification = EXCLUDED.subclassification,
            location = EXCLUDED.location,
            work_type = EXCLUDED.work_type,
            work_arrangement = EXCLUDED.work_arrangement,
            salary_label = EXCLUDED.salary_label,
            listing_date = EXCLUDED.listing_date,
            url = EXCLUDED.url,
            role_id = EXCLUDED.role_id,
            display_type = EXCLUDED.display_type,
            is_featured = EXCLUDED.is_featured,
            bullet_points = EXCLUDED.bullet_points,
            tags = EXCLUDED.tags,
            raw_json = EXCLUDED.raw_json,
            content_hash = EXCLUDED.content_hash,
            content_changed_at = CASE
                WHEN jobs.content_hash IS DISTINCT FROM EXCLUDED.content_hash
                THEN NOW() ELSE jobs.content_changed_at
            END,
            last_seen_at = NOW(),
            delisted_at = NULL
    """, (
        job_id,
        job.get("title"),
        job.get("teaser"),
        job.get("companyName"),
        (job.get("advertiser") or {}).get("id"),
        (classif.get("classification") or {}).get("description"),
        (classif.get("subclassification") or {}).get("description"),
        location,
        work_type,
        work_arrangement,
        job.get("salaryLabel"),
        job.get("listingDate"),
        "https://www.seek.com.au/job/" + job_id,
        job.get("roleId"),
        job.get("displayType"),
        bool(job.get("isFeatured")),
        bullet_points or None,
        tags or None,
        Jsonb(job),
        chash,
    ))

    if is_new:
        log_history(conn, job_id, "first_seen", content_hash=chash, raw_json=job)
        return "first_seen"
    if was_delisted:
        log_history(conn, job_id, "relisted", content_hash=chash, raw_json=job)
        return "relisted"
    if prev_hash is not None and prev_hash != chash:
        log_history(conn, job_id, "changed", content_hash=chash, raw_json=job)
        return "changed"
    return None


def upsert_job_details(conn, job_id, meta, markdown, source_hash):
    conn.execute("""
        INSERT INTO job_details
        (id, title, company, location, work_type, salary, rating, classifications, url, markdown, source_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            company = EXCLUDED.company,
            location = EXCLUDED.location,
            work_type = EXCLUDED.work_type,
            salary = EXCLUDED.salary,
            rating = EXCLUDED.rating,
            classifications = EXCLUDED.classifications,
            url = EXCLUDED.url,
            markdown = EXCLUDED.markdown,
            source_hash = EXCLUDED.source_hash,
            cleaned_at = NOW()
    """, (
        job_id,
        meta.get("title"),
        meta.get("company"),
        meta.get("location"),
        meta.get("work_type"),
        meta.get("salary"),
        meta.get("rating"),
        meta.get("classifications") or None,
        meta.get("url"),
        markdown,
        source_hash,
    ))


def hash_html(html):
    return hashlib.sha256(html.encode()).hexdigest()


def upsert_job_html(conn, job_id, html):
    new_hash = hash_html(html)
    prev = conn.execute(
        "SELECT html_hash FROM jobs WHERE id = %s", (job_id,)
    ).fetchone()
    prev_hash = prev[0] if prev else None
    conn.execute(
        "UPDATE jobs SET raw_html = %s, html_hash = %s, html_fetched_at = NOW() WHERE id = %s",
        (html, new_hash, job_id),
    )
    return prev_hash, new_hash


def mark_expired(conn, job_id, html):
    new_hash = hash_html(html)
    prev = conn.execute(
        "SELECT expired_at FROM jobs WHERE id = %s", (job_id,)
    ).fetchone()
    was_expired = bool(prev and prev[0] is not None)
    conn.execute(
        """UPDATE jobs SET
            raw_html = %s,
            html_hash = %s,
            html_fetched_at = NOW(),
            expired_at = COALESCE(expired_at, NOW())
        WHERE id = %s""",
        (html, new_hash, job_id),
    )
    if not was_expired:
        log_history(conn, job_id, "expired", html_hash=new_hash)
    return was_expired


def sweep_delisted(conn, run_started_at):
    rows = conn.execute("""
        UPDATE jobs SET delisted_at = NOW()
        WHERE last_seen_at IS NOT NULL
          AND last_seen_at < %s
          AND delisted_at IS NULL
          AND expired_at IS NULL
        RETURNING id
    """, (run_started_at,)).fetchall()
    for (job_id,) in rows:
        log_history(conn, job_id, "delisted")
    return len(rows)


def purge_stranded(conn):
    # delisted/expired with no body will never be fetchable - drop them
    rows = conn.execute("""
        DELETE FROM jobs
        WHERE (delisted_at IS NOT NULL OR expired_at IS NOT NULL)
          AND raw_html IS NULL
        RETURNING id
    """).fetchall()
    return len(rows)


if __name__ == "__main__":
    init()
    print("initialized", database_url)
