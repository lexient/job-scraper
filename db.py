#!/usr/bin/env python3

import hashlib
import os

import psycopg
from psycopg.types.json import Jsonb
from dotenv import load_dotenv


load_dotenv(override=True)

database_url = os.environ.get("DATABASE_URL", "postgresql://seek:seek@localhost:5432/seek")


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
    raw_json JSONB,
    raw_html TEXT,
    html_hash TEXT,
    html_fetched_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW()
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
"""


def connect():
    return psycopg.connect(database_url)


def init():
    conn = connect()
    conn.execute(schema)
    conn.commit()
    conn.close()


def upsert_job(conn, job):
    job_id = str(job["id"])
    classif = (job.get("classifications") or [{}])[0]
    location = (job.get("locations") or [{}])[0].get("label")
    work_type = (job.get("workTypes") or [None])[0]
    work_arrangement = (job.get("workArrangements") or {}).get("displayText")

    conn.execute("""
        INSERT INTO jobs
        (id, title, teaser, company, advertiser_id, classification, subclassification,
         location, work_type, work_arrangement, salary_label, listing_date, url, raw_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            raw_json = EXCLUDED.raw_json
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
        Jsonb(job),
    ))


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
    conn.execute(
        "UPDATE jobs SET raw_html = %s, html_hash = %s, html_fetched_at = NOW() WHERE id = %s",
        (html, hash_html(html), job_id),
    )


if __name__ == "__main__":
    init()
    print("initialized", database_url)
