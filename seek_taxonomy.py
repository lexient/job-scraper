#!/usr/bin/env python3

from curl_cffi import requests
import html
import json
import re
import time


# parent and sub classifications are rendered as checkbox filters on /jobs.
# data-automation=<id>, aria-label=<name>. filtering by classification reveals its subs
session = requests.Session()


def parse_checkboxes(page_html):
    pattern = r'data-automation="(\d{4,5})"[^>]*?aria-label="([^"]*)"'
    matches = re.findall(pattern, page_html)
    return [(id_val, html.unescape(name).strip()) for id_val, name in matches]


# step 1: unfiltered /jobs page exposes all parent classifications
print("fetching parent classifications")
response = session.get("https://www.seek.com.au/jobs", impersonate="chrome100")
parent_ids = dict(parse_checkboxes(response.text))
print("found", len(parent_ids), "parents")


# step 2: for each parent, /jobs?classification=<id> adds its subs to the sidebar
taxonomy = {}
for i, parent_id in enumerate(sorted(parent_ids, key=int)):
    parent_name = parent_ids[parent_id]
    print(" ", str(i + 1) + "/" + str(len(parent_ids)), parent_id, "-", parent_name)

    if i > 0:
        time.sleep(1)

    response = session.get("https://www.seek.com.au/jobs?classification=" + parent_id, impersonate="chrome100")
    items = parse_checkboxes(response.text)

    # subs are whatever ids appear under this parent that arent themselves parents
    subs = {}
    for sub_id, name in items:
        if sub_id not in parent_ids:
            subs[sub_id] = name

    taxonomy[parent_id] = {
        "name": parent_name,
        "subclassifications": dict(sorted(subs.items(), key=lambda x: int(x[0]))),
    }
    print("     ->", len(subs), "subclassifications")


# summary
print()
total_subs = 0
for cid in sorted(taxonomy, key=int):
    entry = taxonomy[cid]
    n = len(entry["subclassifications"])
    total_subs = total_subs + n
    print(" ", cid, "-", entry["name"], "(" + str(n), "subs)")
print()
print("total:", len(taxonomy), "classifications,", total_subs, "subclassifications")


output_path = "seek_taxonomy.json"
file = open(output_path, "w")
json.dump(taxonomy, file, indent=2, ensure_ascii=False)
file.close()
print("saved to", output_path)
