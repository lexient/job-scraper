#!/usr/bin/env python3

from bs4 import BeautifulSoup
import markdownify
import os
import yaml


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


# make folder for markdown output if it doesnt exist
if not os.path.exists("jobs_md"):
    os.makedirs("jobs_md")


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

    meta = {"id": job_id}
    for key, marker in meta_fields.items():
        meta[key] = extract_text(soup, marker)
    meta["classifications"] = extract_classifications(soup)
    meta["url"] = "https://www.seek.com.au/job/" + job_id

    md_body = markdownify.markdownify(str(body), heading_style="ATX").strip()

    out_path = "jobs_md/" + job_id + ".md"
    out_file = open(out_path, "w")
    out_file.write("---\n")
    yaml.safe_dump(meta, out_file, sort_keys=False, allow_unicode=True)
    out_file.write("---\n\n")
    out_file.write(md_body)
    out_file.write("\n")
    out_file.close()

    converted = converted + 1
    print(converted, job_id)

print()
print("converted", converted, "files")
