#!/usr/bin/env python3

from curl_cffi import requests
import os
import sys
import time


# https://curl-cffi.readthedocs.io/en/latest/quick_start.html#requests-like
session = requests.Session()


# search caps at page 27 (see find_pagination_limit.py) = 540 results per query
max_results_per_query = 20 * 27


# classification 6281 (ICT). reseed from seek's frontend subclassification dropdown
subclassifications = [
    "6282", "6283", "6284", "6285", "6286", "6287", "6288", "6289",
    "6290", "6291", "6292", "6293", "6294", "6295", "6296", "6297",
    "6298", "6299", "6300", "6301", "6302", "6303",
]


# get limit from command line
if len(sys.argv) > 1:
    limit = int(sys.argv[1])
else:
    limit = 5


# make folder for jobs if it doesnt exist
if not os.path.exists("jobs"):
    os.makedirs("jobs")


jobs_saved = 0

for sub_id in subclassifications:
    if jobs_saved >= limit:
        break

    page = 1
    while jobs_saved < limit:
        search_url = "https://www.seek.com.au/api/jobsearch/v5/search?subclassification=" + sub_id + "&page=" + str(page)
        search_response = session.get(search_url, impersonate="chrome100")
        search_results = search_response.json()

        if page == 1:
            sub_total = search_results["totalCount"]
            print("subclassification", sub_id, "-", sub_total, "jobs")
            if sub_total > max_results_per_query:
                print("  warning: exceeds cap of", max_results_per_query, "- only top", max_results_per_query, "will be fetched")

        jobs = search_results["data"]
        if len(jobs) == 0:
            break

        for job in jobs:
            job_id = job["id"]
            job_title = job["title"]

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

        page = page + 1
