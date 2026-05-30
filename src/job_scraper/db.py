#!/usr/bin/env python3

import hashlib
import os

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

load_dotenv(override=True)

_port = os.environ.get("POSTGRES_HOST_PORT", "5432")
database_url = os.environ.get(
    "DATABASE_URL", f"postgresql://seek:seek@localhost:{_port}/postgres"
)


def connect():
    return psycopg.connect(database_url)


def log_history(
    conn,
    source,
    job_id,
    event,
    content_hash=None,
    html_hash=None,
    raw_json=None,
    markdown=None,
):
    conn.execute(
        """
        INSERT INTO job_history (source, job_id, event, content_hash, html_hash, raw_json, markdown)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            source,
            job_id,
            event,
            content_hash,
            html_hash,
            Jsonb(raw_json) if raw_json is not None else None,
            markdown,
        ),
    )


def upsert_job(conn, source, job_id, fields, raw_json, chash):
    prev = conn.execute(
        "SELECT content_hash, delisted_at FROM jobs WHERE source = %s AND id = %s",
        (source, job_id),
    ).fetchone()
    is_new = prev is None
    prev_hash = prev[0] if prev else None
    was_delisted = bool(prev and prev[1] is not None)

    conn.execute(
        """
        INSERT INTO jobs
        (id, source, title, teaser, company, advertiser_id, classification, subclassification,
         location, work_type, work_arrangement, salary_label, listing_date, url,
         role_id, display_type, is_featured, bullet_points, tags, raw_json,
         content_hash, content_changed_at, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, NOW(), NOW())
        ON CONFLICT (id, source) DO UPDATE SET
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
            misses = 0,
            delisted_at = NULL
    """,
        (
            job_id,
            source,
            fields.get("title"),
            fields.get("teaser"),
            fields.get("company"),
            fields.get("advertiser_id"),
            fields.get("classification"),
            fields.get("subclassification"),
            fields.get("location"),
            fields.get("work_type"),
            fields.get("work_arrangement"),
            fields.get("salary_label"),
            fields.get("listing_date"),
            fields.get("url"),
            fields.get("role_id"),
            fields.get("display_type"),
            fields.get("is_featured"),
            fields.get("bullet_points"),
            fields.get("tags"),
            Jsonb(raw_json),
            chash,
        ),
    )

    if is_new:
        log_history(
            conn, source, job_id, "first_seen", content_hash=chash, raw_json=raw_json
        )
        return "first_seen"
    if was_delisted:
        log_history(
            conn, source, job_id, "relisted", content_hash=chash, raw_json=raw_json
        )
        return "relisted"
    if prev_hash is not None and prev_hash != chash:
        log_history(
            conn, source, job_id, "changed", content_hash=chash, raw_json=raw_json
        )
        return "changed"
    return None


def upsert_job_details(conn, source, job_id, meta, markdown, source_hash):
    conn.execute(
        """
        INSERT INTO job_details
        (id, source, title, company, location, work_type, salary, rating, classifications, url, markdown, source_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id, source) DO UPDATE SET
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
    """,
        (
            job_id,
            source,
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
        ),
    )


def hash_html(html):
    return hashlib.sha256(html.encode()).hexdigest()


def upsert_job_html(conn, source, job_id, html):
    new_hash = hash_html(html)
    prev = conn.execute(
        "SELECT html_hash FROM jobs WHERE source = %s AND id = %s",
        (source, job_id),
    ).fetchone()
    prev_hash = prev[0] if prev else None
    conn.execute(
        """UPDATE jobs SET raw_html = %s, html_hash = %s, html_fetched_at = NOW()
           WHERE source = %s AND id = %s""",
        (html, new_hash, source, job_id),
    )
    return prev_hash, new_hash


def mark_expired(conn, source, job_id, html):
    new_hash = hash_html(html)
    prev = conn.execute(
        "SELECT expired_at FROM jobs WHERE source = %s AND id = %s",
        (source, job_id),
    ).fetchone()
    was_expired = bool(prev and prev[0] is not None)
    conn.execute(
        """UPDATE jobs SET
            raw_html = %s,
            html_hash = %s,
            html_fetched_at = NOW(),
            expired_at = COALESCE(expired_at, NOW())
        WHERE source = %s AND id = %s""",
        (html, new_hash, source, job_id),
    )
    if not was_expired:
        log_history(conn, source, job_id, "expired", html_hash=new_hash)
    return was_expired


def sweep_delisted(conn, source, run_started_at, miss_threshold):
    conn.execute(
        """
        UPDATE jobs SET misses = misses + 1
        WHERE source = %s
          AND last_seen_at IS NOT NULL
          AND last_seen_at < %s
          AND delisted_at IS NULL
          AND expired_at IS NULL
    """,
        (source, run_started_at),
    )
    rows = conn.execute(
        """
        UPDATE jobs SET delisted_at = NOW()
        WHERE source = %s
          AND misses >= %s
          AND delisted_at IS NULL
          AND expired_at IS NULL
        RETURNING id
    """,
        (source, miss_threshold),
    ).fetchall()
    for (job_id,) in rows:
        log_history(conn, source, job_id, "delisted")
    return len(rows)


def purge_stranded(conn, source):
    rows = conn.execute(
        """
        DELETE FROM jobs
        WHERE source = %s
          AND (delisted_at IS NOT NULL OR expired_at IS NOT NULL)
          AND raw_html IS NULL
        RETURNING id
        """,
        (source,),
    ).fetchall()
    return len(rows)
