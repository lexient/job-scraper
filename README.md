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
python scrape.py
## or scrape.py [limit]
```
