# seek-scrape

Scrapes jobs from seek.com.au.

The search API (/api/jobsearch/v5/search) is public, however the API for fetching the content of the job listings is not.

This script obtains job IDs from the search API and downloads the HTML of the job pages themselves.

Cloudflare detection is bypassed using a browser's TLS/JA3 fingerprint and HTTP/2 behaviour using [curl_cffi](https://github.com/lexiforest/curl_cffi).

## Usage

```bash
git clone https://github.com/lexient/seek-scrape
cd seek-scrape

# set up venv
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# scrape - downloads html to jobs/ and writes api data to seek.db
python scrape.py
## or scrape.py [limit]

# extract markdown + metadata from the scraped html into seek.db
python clean.py
```

## Pagination

The search API caps at 27 pages of 20 jobs = 540 results per query, even if `totalCount` is higher (e.g. 7616 for classification=6281). Anything past page 27 is silently truncated, so a single broad call misses most jobs.

To get full coverage the script splits the query by subclassification. Any subclassification still over 540 gets split again by region, and so on through the `fallbacks` list in `scrape.py`. If a query still exceeds 540 after every fallback is applied, the script raises.

## Taxonomy

`scrape.py` loads subclassifications from `seek_taxonomy.json` at startup, keyed by `classification_id`. To target a different category, change that variable.

`seek_taxonomy.py` rebuilds the taxonomy by scraping the classification/subclassification checkboxes from seek's `/jobs` filter sidebar. Re-run it when seek adds or renames categories.

```bash
python seek_taxonomy.py
```

## Cleaning

`clean.py` walks `jobs/*.html`, extracts the job ad body (via `data-automation="jobAdDetails"` with `"jobDescription"` as fallback), pulls metadata fields (title, company, location, work type, salary, classifications, rating, url), converts the body to markdown, and upserts into the `job_details` table.

```bash
python clean.py
```

## Database

All data lives in `seek.db` (sqlite). Two tables, linked by job `id`:

- `jobs` — one row per listing returned by the search API (`scrape.py` populates this, including the full response as `raw_json` for reprocessing).
- `job_details` — one row per scraped detail page (`clean.py` populates this with markdown and extracted fields).

Schema is created automatically on first connect. To init explicitly:

```bash
python db.py
```

Query with the sqlite cli:

```bash
sqlite3 seek.db
sqlite> SELECT COUNT(*) FROM jobs;
sqlite> SELECT j.title, j.company, d.rating FROM jobs j JOIN job_details d USING(id) LIMIT 10;
```
