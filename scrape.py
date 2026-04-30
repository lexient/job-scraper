#!/usr/bin/env python3

from curl_cffi import requests
from urllib.parse import quote
from db import connect, upsert_job
import json
import os
import sys
import time


# https://curl-cffi.readthedocs.io/en/latest/quick_start.html#requests-like
session = requests.Session()


# search caps at page 27 (see find_pagination_limit.py) = 540 results per query
max_results_per_query = 20 * 27


# subclassifications come from seek_taxonomy.json - rerun seek_taxonomy.py to refresh
classification_id = "6281"  # Information & Communication Technology

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


# fallbacks to split an over-cap query by, tried in order. add more as needed
fallbacks = [
    ("where", regions),
]


# get limit from command line
if len(sys.argv) > 1:
    limit = int(sys.argv[1])
else:
    limit = 5


# make folder for jobs if it doesnt exist
if not os.path.exists("jobs"):
    os.makedirs("jobs")


db = connect()


search_base = "https://www.seek.com.au/api/jobsearch/v5/search?"


def count(query):
    response = session.get(search_base + query + "&page=1", impersonate="chrome100")
    return response.json()["totalCount"]


# count each sub, then progressively split over-cap queries by each fallback
queries = []
for s in subclassifications:
    q = "subclassification=" + s
    total = count(q)
    print("subclassification", s, "-", total, "jobs")
    queries.append((q, total))

for param, values in fallbacks:
    refined = []
    for q, total in queries:
        if total <= max_results_per_query:
            refined.append((q, total))
        else:
            print("splitting", q, "(" + str(total), "jobs) by", param)
            for v in values:
                sub_q = q + "&" + param + "=" + quote(v)
                refined.append((sub_q, count(sub_q)))
    queries = refined


for q, total in queries:
    if total > max_results_per_query:
        raise Exception("query '" + q + "' has " + str(total) + " jobs, exceeds cap. no more fallbacks to split by.")


# scrape each query, paginating until we hit the limit or run out
jobs_saved = 0

for q, total in queries:
    if jobs_saved >= limit:
        break

    page = 1
    while jobs_saved < limit:
        search_url = search_base + q + "&page=" + str(page)
        search_response = session.get(search_url, impersonate="chrome100")
        jobs = search_response.json()["data"]

        if len(jobs) == 0:
            break

        for job in jobs:
            job_id = job["id"]
            job_title = job["title"]

            # upsert the api listing data regardless of whether we download the html
            upsert_job(db, job)

            filename = "jobs/" + str(job_id) + ".html"
            if os.path.exists(filename):
                continue

            job_url = "https://www.seek.com.au/job/" + str(job_id)
            job_response = session.get(job_url, impersonate="chrome100")
            job_html = job_response.text

            file = open(filename, "w")
            file.write(job_html)
            file.close()

            print(jobs_saved + 1, job_id, "-", job_title)
            jobs_saved = jobs_saved + 1

            if jobs_saved >= limit:
                break

        db.commit()
        page = page + 1

db.close()
