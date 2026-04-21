#!/usr/bin/env python3

from curl_cffi import requests
import time


session = requests.Session()


# binary search for the highest page that still returns jobs
lo = 1
hi = 1000


# check the upper bound first
url = "https://www.seek.com.au/api/jobsearch/v5/search?classification=6281&page=" + str(hi)
response = session.get(url, impersonate="chrome100")
data = response.json()
n = len(data["data"])
print("page", hi, "-", n, "jobs")


# if page 1000 still has jobs, keep doubling until we find an empty page
while n > 0:
    lo = hi
    hi = hi * 2
    url = "https://www.seek.com.au/api/jobsearch/v5/search?classification=6281&page=" + str(hi)
    response = session.get(url, impersonate="chrome100")
    data = response.json()
    n = len(data["data"])
    print("page", hi, "-", n, "jobs")
    if hi > 20000:
        break


# binary search between lo (has jobs) and hi (empty)
print()
print("searching between", lo, "and", hi)

while lo + 1 < hi:
    mid = (lo + hi) // 2
    url = "https://www.seek.com.au/api/jobsearch/v5/search?classification=6281&page=" + str(mid)
    response = session.get(url, impersonate="chrome100")
    data = response.json()
    n = len(data["data"])
    print("page", mid, "-", n, "jobs")
    
    if n > 0:
        lo = mid
    else:
        hi = mid



print()
print("last page with jobs:", lo)