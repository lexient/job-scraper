#!/usr/bin/env python3

from curl_cffi import requests
import os
import sys
import time


# https://curl-cffi.readthedocs.io/en/latest/quick_start.html#requests-like
session = requests.Session()


# get limit from command line
if len(sys.argv) > 1:
    limit = int(sys.argv[1])
else:
    limit = 5
    

# make folder for jobs if it doesnt exist
if not os.path.exists("jobs"):
    os.makedirs("jobs")


page = 1
jobs_saved = 0

while jobs_saved < limit:
    # get search results for this page
    search_url = "https://www.seek.com.au/api/jobsearch/v5/search?classification=6281&page=" + str(page)
    search_response = session.get(search_url, impersonate="chrome100")
    search_results = search_response.json()
    # print(search_results)
    jobs = search_results["data"]

    for job in jobs:
        job_id = job["id"]
        job_title = job["title"]
        
        job_url = "https://www.seek.com.au/job/" + str(job_id)
        job_response = session.get(job_url, impersonate="chrome100")
        job_html = job_response.text
        
        filename = "jobs/" + str(job_id) + ".html"
        file = open(filename, "w")
        file.write(job_html)
        file.close()
        
        print(jobs_saved + 1, job_id, "-", job_title)
        jobs_saved = jobs_saved + 1
        
        if jobs_saved >= limit:
            break
    
    page = page + 1