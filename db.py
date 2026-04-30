#!/usr/bin/env python3

import json
import sqlite3


db_path = "seek.db"


# jobs = data from the /search api response
# job_details = data extracted from the /job/<id> html page (body + frontmatter fields)
# linked by id (no FK so clean.py can run on pre-existing html without a jobs row)
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


def upsert_job_details(conn, job_id, meta, markdown):
    conn.execute("""
        INSERT OR REPLACE INTO job_details
        (id, title, company, location, work_type, salary, rating, classifications, url, markdown)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    ))


if __name__ == "__main__":
    conn = connect()
    conn.close()
    print("initialized", db_path)
