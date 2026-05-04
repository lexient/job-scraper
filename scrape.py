#!/usr/bin/env python3

from bs4 import BeautifulSoup
from curl_cffi import AsyncSession
from urllib.parse import quote
from db import connect, hash_html, upsert_job, upsert_job_details, upsert_job_html
import asyncio
import json
import log
import markdownify
import sys
import time

search_endpoint = "https://www.seek.com.au/api/jobsearch/v5/search?"
classification_id = "6281"  # Information & Communication Technology

# 20 results per page, 27 pages max per query
max_results_per_query = 20 * 27

concurrency = 8
delay = 0.05
retry_waits = [1, 2, 4, 8, 16, 32, 64]

taxonomy_file = open("seek_taxonomy.json")
taxonomy = json.load(taxonomy_file)
taxonomy_file.close()
subclassifications = list(taxonomy[classification_id]["subclassifications"].keys())


regions = [
    "All Perth WA",
    "All Sydney NSW",
    "All Melbourne VIC",
    "All Brisbane QLD",
    "All Gold Coast QLD",
    "All Adelaide SA",
    "All Canberra ACT",
    "All Hobart TAS",
    "All Darwin NT",
]


fallbacks = [
    ("where", regions),
]


if len(sys.argv) > 1:
    limit = int(sys.argv[1])
else:
    limit = 5


db = connect()


async def count(session, sem, query):
    async with sem:
        response = await session.get(search_endpoint + query + "&page=1", impersonate="chrome146")
        return response.json()["totalCount"]


async def fetch_page(session, sem, query, page):
    async with sem:
        response = await session.get(search_endpoint + query + "&page=" + str(page), impersonate="chrome146")
        return response.json()["data"]


# shadow-blocked: 200 with empty react shell
def is_blocked(html):
    return "jobAdDetails" not in html and "jobDescription" not in html


body_selectors = [
    {"data-automation": "jobAdDetails"},
    {"data-automation": "jobDescription"},
]

meta_fields = {
    "title": "job-detail-title",
    "company": "advertiser-name",
    "location": "job-detail-location",
    "work_type": "job-detail-work-type",
    "salary": "job-detail-salary",
    "rating": "company-review",
}


def _extract_text(soup, marker):
    el = soup.find(attrs={"data-automation": marker})
    if not el:
        return None
    return el.get_text(strip=True) or None


def _extract_classifications(soup):
    el = soup.find(attrs={"data-automation": "job-detail-classifications"})
    if not el:
        return []
    return [a.get_text(strip=True) for a in el.find_all("a")]


# None means body marker is missing - layout change
def parse_job_html(html, job_id):
    soup = BeautifulSoup(html, "lxml")
    body = None
    for attrs in body_selectors:
        body = soup.find("div", attrs=attrs)
        if body:
            break
    if not body:
        return None
    meta = {k: _extract_text(soup, m) for k, m in meta_fields.items()}
    meta["classifications"] = _extract_classifications(soup)
    meta["url"] = "https://www.seek.com.au/job/" + job_id
    md = markdownify.markdownify(str(body), heading_style="ATX").strip()
    return meta, md


async def fetch_and_save(session, sem, job, idx, total_n):
    url = "https://www.seek.com.au/job/" + str(job["id"])
    job_id = str(job["id"])
    async with sem:
        await asyncio.sleep(delay)
        for attempt in range(len(retry_waits) + 1):
            response = await session.get(url, impersonate="chrome100")
            if not is_blocked(response.text):
                html = response.text
                upsert_job_html(db, job_id, html)
                parsed = parse_job_html(html, job_id)
                if parsed is not None:
                    meta, markdown = parsed
                    upsert_job_details(db, job_id, meta, markdown, hash_html(html))
                else:
                    log.error(idx, "/", total_n, job_id, "- saved html but couldnt parse body")
                db.commit()
                log.info(idx, "/", total_n, job_id, "-", job["title"])
                return "added"
            # semaphore slot is held through the waits
            if attempt < len(retry_waits):
                wait = retry_waits[attempt]
                log.warn(idx, "/", total_n, job_id, "- blocked, retry in", wait, "s")
                await asyncio.sleep(wait)
        log.error(idx, "/", total_n, job_id, "- blocked after retries")
        return "blocked"


async def main():
    async with AsyncSession(max_clients=concurrency) as session:
        sem = asyncio.Semaphore(concurrency)

        queries_base = ["subclassification=" + s for s in subclassifications]
        totals = await asyncio.gather(*[count(session, sem, q) for q in queries_base])
        queries = list(zip(queries_base, totals))
        for q, t in queries:
            sub_id = q.split("=")[1]
            name = taxonomy[classification_id]["subclassifications"].get(sub_id, sub_id)
            log.info("subclassification", name, "-", t, "jobs")

        for param, values in fallbacks:
            refined = []
            over_queries = []
            for q, total in queries:
                if total <= max_results_per_query:
                    refined.append((q, total))
                else:
                    log.info("splitting", q, "(" + str(total), "jobs) by", param)
                    for v in values:
                        over_queries.append(q + "&" + param + "=" + quote(v))
            over_totals = await asyncio.gather(*[count(session, sem, q) for q in over_queries])
            refined.extend(zip(over_queries, over_totals))
            queries = refined

        for q, total in queries:
            if total > max_results_per_query:
                raise Exception("query '" + q + "' has " + str(total) + " jobs, exceeds cap. no more fallbacks to split by.")

        search_tasks = []
        for q, total in queries:
            pages_needed = min(27, (total + 19) // 20)
            for page in range(1, pages_needed + 1):
                search_tasks.append(fetch_page(session, sem, q, page))
        log.info("fetching", len(search_tasks), "search pages")
        all_pages = await asyncio.gather(*search_tasks)

        all_jobs = []
        for jobs in all_pages:
            for job in jobs:
                all_jobs.append(job)

        log.info("collected", len(all_jobs), "listings")

        for job in all_jobs:
            upsert_job(db, job)
        db.commit()

        have_html = {r[0] for r in db.execute(
            "SELECT id FROM jobs WHERE raw_html IS NOT NULL"
        ).fetchall()}
        to_fetch = []
        seen = set()
        for job in all_jobs:
            job_id = str(job["id"])
            if job_id in seen or job_id in have_html:
                continue
            seen.add(job_id)
            to_fetch.append(job)

        already_have = len(have_html & {str(j["id"]) for j in all_jobs})
        to_fetch = to_fetch[:limit]
        log.info("downloading", len(to_fetch), "job pages (" + str(already_have), "already in db)")

        results = await asyncio.gather(*[
            fetch_and_save(session, sem, job, i + 1, len(to_fetch))
            for i, job in enumerate(to_fetch)
        ])

    db.close()

    added = results.count("added")
    blocked = results.count("blocked")
    log.info("added", added, "- blocked", blocked, "- skipped", already_have)


start = time.time()
asyncio.run(main())
elapsed = int(time.time() - start)
log.info("completed in", elapsed // 60, "m", elapsed % 60, "s")
