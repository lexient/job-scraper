#!/usr/bin/env python3

from bs4 import BeautifulSoup
from curl_cffi import AsyncSession
from datetime import datetime, timezone
from urllib.parse import quote
from db import (
    connect, log_history, mark_expired, purge_stranded, sweep_delisted,
    upsert_job, upsert_job_details, upsert_job_html,
)
import asyncio
import json
import log
import markdownify
import os
import sys
import time

search_endpoint = "https://www.seek.com.au/api/jobsearch/v5/search?"
classification_id = "6281"  # Information & Communication Technology

# 20 results per page, 27 pages max per query
max_results_per_query = 20 * 27

concurrency = int(os.environ.get("CONCURRENCY", "8"))
delay = 0.1
retry_waits = [1, 2, 4, 8, 16, 32]

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





def _parse_search(response, ctx):
    try:
        return response.json()
    except Exception:
        log.error(ctx, "- status", response.status_code, "ct", response.headers.get("content-type"), "body:", response.text[:300])
        raise


async def count(session, sem, query):
    async with sem:
        response = await session.get(search_endpoint + query + "&page=1", impersonate="chrome146")
        return _parse_search(response, "count " + query)["totalCount"]


async def fetch_page(session, sem, query, page):
    async with sem:
        try:
            response = await session.get(search_endpoint + query + "&page=" + str(page), impersonate="chrome146")
            return _parse_search(response, "page " + str(page) + " " + query)["data"]
        except Exception as e:
            log.error("page", page, query, "- dropped:", repr(e)[:120])
            return None


# shadow-blocked: 200 with empty react shell
def is_blocked(html):
    return "jobAdDetails" not in html and "jobDescription" not in html


# expired ads 200 with an expiredJobPage container; without this we'd retry forever
def is_expired(html):
    return 'data-automation="expiredJobPage"' in html


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
            if is_expired(response.text):
                mark_expired(db, job_id, response.text)
                db.commit()
                log.info(idx, "/", total_n, job_id, "- expired")
                return "expired"
            if not is_blocked(response.text):
                html = response.text
                prev_hash, new_hash = upsert_job_html(db, job_id, html)
                parsed = parse_job_html(html, job_id)
                if parsed is not None:
                    meta, markdown = parsed
                    upsert_job_details(db, job_id, meta, markdown, new_hash)
                    if prev_hash is not None and prev_hash != new_hash:
                        log_history(db, job_id, "html_changed", html_hash=new_hash, markdown=markdown)
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
    # curl_cffi default max_clients is 10. https://curl-cffi.readthedocs.io/en/latest/api.html
    async with AsyncSession(max_clients=concurrency) as session:
        sem = asyncio.Semaphore(concurrency)

        queries_base = ["subclassification=" + s for s in subclassifications]
        totals = await asyncio.gather(*[count(session, sem, q) for q in queries_base])
        queries = list(zip(queries_base, totals))
        for q, t in queries:
            sub_id = q.split("=")[1]
            name = taxonomy[classification_id]["subclassifications"].get(sub_id, sub_id)
            log.info(name, "-", t, "jobs")

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
        dropped_pages = sum(1 for p in all_pages if p is None)
        partial_sweep = dropped_pages > 0

        all_jobs = []
        for jobs in all_pages:
            if jobs is None:
                continue
            for job in jobs:
                all_jobs.append(job)

        log.info("collected", len(all_jobs), "listings" + (" (" + str(dropped_pages) + " pages dropped)" if dropped_pages else ""))

        # track ids whose listing changed so phase 2 re-fetches even if raw_html exists
        refetch_ids = set()
        new_count = 0
        changed_count = 0
        relisted_count = 0
        for job in all_jobs:
            event = upsert_job(db, job)
            if event == "first_seen":
                new_count += 1
            elif event == "changed":
                changed_count += 1
                refetch_ids.add(str(job["id"]))
            elif event == "relisted":
                relisted_count += 1
                refetch_ids.add(str(job["id"]))
        db.commit()
        log.info("phase 1 -", new_count, "new,", changed_count, "changed,", relisted_count, "relisted")

        # dedup ids that appear under multiple queries; skip ids with raw_html unless changed
        have_html = {r[0] for r in db.execute(
            "SELECT id FROM jobs WHERE raw_html IS NOT NULL"
        ).fetchall()}
        to_fetch = []
        seen = set()
        for job in all_jobs:
            job_id = str(job["id"])
            if job_id in seen:
                continue
            if job_id in have_html and job_id not in refetch_ids:
                continue
            seen.add(job_id)
            to_fetch.append(job)

        already_have = len(have_html & {str(j["id"]) for j in all_jobs}) - len(refetch_ids & have_html)
        to_fetch = to_fetch[:limit]
        log.info("downloading", len(to_fetch), "job pages (" + str(already_have), "already in db)")

        results = await asyncio.gather(*[
            fetch_and_save(session, sem, job, i + 1, len(to_fetch))
            for i, job in enumerate(to_fetch)
        ])

        if partial_sweep:
            log.warn("partial sweep, skipping delisted sweep")
            delisted = 0
        else:
            delisted = sweep_delisted(db, run_started_at)
        purged = purge_stranded(db)
        db.commit()

    db.close()

    added = results.count("added")
    expired = results.count("expired")
    blocked = results.count("blocked")
    log.info("added", added, "- expired", expired, "- blocked", blocked, "- skipped", already_have, "- delisted", delisted, "- purged", purged)


start = time.time()
run_started_at = datetime.now(timezone.utc)
asyncio.run(main())
elapsed = int(time.time() - start)
log.info("completed in", elapsed // 60, "m", elapsed % 60, "s")
