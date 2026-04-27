#!/usr/bin/env python3

from bs4 import BeautifulSoup
import markdownify
import os


# selectors for the job ad body on a seek listing page, in preference order
selectors = [
    {"data-automation": "jobAdDetails"},
    {"data-automation": "jobDescription"},
]


# make folder for markdown output if it doesnt exist
if not os.path.exists("jobs_md"):
    os.makedirs("jobs_md")


converted = 0

for filename in sorted(os.listdir("jobs")):
    if not filename.endswith(".html"):
        continue

    job_id = filename[:-5]
    out_path = "jobs_md/" + job_id + ".md"

    html_file = open("jobs/" + filename)
    html = html_file.read()
    html_file.close()

    soup = BeautifulSoup(html, "lxml")
    ad = None
    for attrs in selectors:
        ad = soup.find("div", attrs=attrs)
        if ad:
            break

    if not ad:
        print("no ad body for", job_id)
        continue

    md = markdownify.markdownify(str(ad), heading_style="ATX").strip()

    out_file = open(out_path, "w")
    out_file.write(md)
    out_file.close()

    converted = converted + 1
    print(converted, job_id)

print()
print("converted", converted, "files")
