#!/usr/bin/env python3

import hashlib
import json
import sqlite3


db_path = "seek.db"


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
    raw_json TEXT,
    raw_html TEXT,
    html_hash TEXT,
    html_fetched_at TEXT,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_details (
    id TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    location TEXT,
    work_type TEXT,
    salary TEXT,
    rating TEXT,
    classifications TEXT,
    url TEXT,
    markdown TEXT,
    source_hash TEXT,
    cleaned_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect():
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    return conn


def upsert_job(conn, job):
    job_id = str(job["id"])
    classif = (job.get("classifications") or [{}])[0]
    location = (job.get("locations") or [{}])[0].get("label")
    work_type = (job.get("workTypes") or [None])[0]
    work_arrangement = (job.get("workArrangements") or {}).get("displayText")

    conn.execute("""
        INSERT OR REPLACE INTO jobs
        (id, title, teaser, company, advertiser_id, classification, subclassification,
         location, work_type, work_arrangement, salary_label, listing_date, url, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        json.dumps(job),
    ))


def upsert_job_details(conn, job_id, meta, markdown, source_hash):
    conn.execute("""
        INSERT OR REPLACE INTO job_details
        (id, title, company, location, work_type, salary, rating, classifications, url, markdown, source_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id,
        meta.get("title"),
        meta.get("company"),
        meta.get("location"),
        meta.get("work_type"),
        meta.get("salary"),
        meta.get("rating"),
        json.dumps(meta.get("classifications", [])),
        meta.get("url"),
        markdown,
        source_hash,
    ))


def hash_html(html):
    return hashlib.sha256(html.encode()).hexdigest()


def upsert_job_html(conn, job_id, html):
    conn.execute(
        "UPDATE jobs SET raw_html = ?, html_hash = ?, html_fetched_at = CURRENT_TIMESTAMP WHERE id = ?",
        (html, hash_html(html), job_id),
    )


if __name__ == "__main__":
    conn = connect()
    conn.close()
    print("initialized", db_path)
