#!/usr/bin/env python3

from bs4 import BeautifulSoup
from db import connect, upsert_job_details
import markdownify
import os


# selectors for the job ad body on a seek listing page, in preference order
body_selectors = [
    {"data-automation": "jobAdDetails"},
    {"data-automation": "jobDescription"},
]


# data-automation markers for single-value metadata fields, in output order
meta_fields = {
    "title": "job-detail-title",
    "company": "advertiser-name",
    "location": "job-detail-location",
    "work_type": "job-detail-work-type",
    "salary": "job-detail-salary",
    "rating": "company-review",
}


def extract_text(soup, marker):
    el = soup.find(attrs={"data-automation": marker})
    if not el:
        return None
    text = el.get_text(strip=True)
    return text or None


def extract_classifications(soup):
    el = soup.find(attrs={"data-automation": "job-detail-classifications"})
    if not el:
        return []
    # each classification is its own <a> under the parent span
    return [a.get_text(strip=True) for a in el.find_all("a")]


db = connect()

converted = 0

for filename in sorted(os.listdir("jobs")):
    if not filename.endswith(".html"):
        continue

    job_id = filename[:-5]

    html_file = open("jobs/" + filename)
    html = html_file.read()
    html_file.close()

    soup = BeautifulSoup(html, "lxml")

    body = None
    for attrs in body_selectors:
        body = soup.find("div", attrs=attrs)
        if body:
            break

    if not body:
        print("no ad body for", job_id)
        continue

    meta = {}
    for key, marker in meta_fields.items():
        meta[key] = extract_text(soup, marker)
    meta["classifications"] = extract_classifications(soup)
    meta["url"] = "https://www.seek.com.au/job/" + job_id

    md = markdownify.markdownify(str(body), heading_style="ATX").strip()

    upsert_job_details(db, job_id, meta, md)

    converted = converted + 1
    print(converted, job_id)

    if converted % 50 == 0:
        db.commit()

db.commit()
db.close()

print()
print("converted", converted, "files")
