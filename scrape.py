#!/usr/bin/env python3

from curl_cffi import AsyncSession
from urllib.parse import quote
from db import connect, upsert_job
import asyncio
import json
import log
import os
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


if not os.path.exists("output/jobs"):
    os.makedirs("output/jobs")


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


async def fetch_and_save(session, sem, job, filename, idx, total_n):
    url = "https://www.seek.com.au/job/" + str(job["id"])
    async with sem:
        await asyncio.sleep(delay)
        for attempt in range(len(retry_waits) + 1):
            response = await session.get(url, impersonate="chrome100")
            if not is_blocked(response.text):
                file = open(filename, "w")
                file.write(response.text)
                file.close()
                log.info(idx, "/", total_n, job["id"], "-", job["title"])
                return "added"
            # semaphore slot is held through the waits
            if attempt < len(retry_waits):
                wait = retry_waits[attempt]
                log.warn(idx, "/", total_n, job["id"], "- blocked, retry in", wait, "s")
                await asyncio.sleep(wait)
        log.error(idx, "/", total_n, job["id"], "- blocked after retries")
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

        to_fetch = []
        seen = set()
        for job in all_jobs:
            job_id = str(job["id"])
            if job_id in seen:
                continue
            seen.add(job_id)
            filename = "output/jobs/" + job_id + ".html"
            if not os.path.exists(filename):
                to_fetch.append((job, filename))

        already_have = len(seen) - len(to_fetch)
        to_fetch = to_fetch[:limit]
        log.info("downloading", len(to_fetch), "job pages (" + str(already_have), "already on disk)")

        results = await asyncio.gather(*[
            fetch_and_save(session, sem, job, filename, i + 1, len(to_fetch))
            for i, (job, filename) in enumerate(to_fetch)
        ])

    db.close()

    added = results.count("added")
    blocked = results.count("blocked")
    log.info("added", added, "- blocked", blocked, "- skipped", already_have)


start = time.time()
asyncio.run(main())
elapsed = int(time.time() - start)
log.info("completed in", elapsed // 60, "m", elapsed % 60, "s")
