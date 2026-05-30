#!/usr/bin/env python3

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote_plus

import markdownify
import nodriver as uc
from bs4 import BeautifulSoup
from nodriver.core.connection import ProtocolException

from job_scraper.db import (
    connect,
    log_history,
    mark_expired,
    purge_stranded,
    sweep_delisted,
    upsert_job,
    upsert_job_details,
    upsert_job_html,
)

SOURCE = "indeed"
BASE = "https://au.indeed.com"

# direct /viewjob hits get a cloudflare challenge, but the search SPA does not, so
# we drive a real browser: load the search page, then click each card to render its
# description in the right pane. browser_args let chromium run under root in docker.
HEADLESS = os.environ.get("HEADLESS", "").lower() in ("1", "true", "yes")
CHROME_PATH = os.environ.get("CHROME_PATH") or None
BROWSER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]
delay = float(os.environ.get("REQUEST_DELAY", "0.1"))
search_delay = float(os.environ.get("SEARCH_DELAY", "1.5"))

# cloudflare flags the session after a few dozen searches and serves a challenge
# that hangs navigation, so we cap each load and stop once it starts blocking. the
# next run rotates the start so coverage builds across runs instead of always
# stalling on the same terms.
NAV_TIMEOUT = 30
MAX_BLOCKS = 5

DELIST_MISSES = 5

classification_id = os.environ.get("CLASSIFICATION_ID", "6281")
with (Path(__file__).parent / "indeed_search_terms.json").open() as f:
    config = json.load(f)[classification_id]
classification_name = config["classification"]
search_terms = config["search_terms"]

# indeed serves only the first result page per query, so we fan out over terms
locations = ["Australia"]


def search_url(keyword, location):
    return f"{BASE}/jobs?q={quote_plus(keyword)}&l={quote_plus(location)}"


def _extract_mosaic_blob(text, key):
    needle = f'window.mosaic.providerData["{key}"]'
    idx = text.find(needle)
    if idx == -1:
        return None
    i = idx + len(needle)
    while i < len(text) and text[i] in " =\t\n":
        i += 1
    if i >= len(text) or text[i] != "{":
        return None
    start = i
    depth = 0
    in_str = False
    esc = False
    while i < len(text):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None
        i += 1
    return None


# cloudflare static page / challenge instead of the real listing
def is_blocked(text):
    return (
        "INDEED_CLOUDFLARE_STATIC_PAGE" in text
        or "_cf_chl_opt" in text
        or "Just a moment" in text
        or "Security Check - Indeed" in text
    )


_content_keys = [
    "title",
    "company",
    "formattedLocation",
    "salarySnippet",
    "jobTypes",
    "remoteLocation",
    "snippet",
    "createDate",
    "pubDate",
    "extractedSalary",
    "taxonomyAttributes",
]


def content_hash(job):
    serial = json.dumps(
        {k: job.get(k) for k in _content_keys}, sort_keys=True, default=str
    )
    return hashlib.sha256(serial.encode()).hexdigest()


def _flatten_tags(job):
    tax = job.get("taxonomyAttributes") or []
    tags = []
    for grp in tax:
        for a in grp.get("attributes") or []:
            label = a.get("label")
            if label:
                tags.append(f"{grp.get('label')}:{label}")
    return tags or None


def _work_type(job):
    tax = job.get("taxonomyAttributes") or []
    for grp in tax:
        if grp.get("label") == "job-types":
            attrs = grp.get("attributes") or []
            if attrs:
                return attrs[0].get("label")
    job_types = job.get("jobTypes") or []
    return job_types[0] if job_types else None


def _listing_date(job):
    ms = job.get("pubDate") or job.get("createDate")
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


# no subclassification, occupation enum (normTitle) -> role_id
def listing_fields(job):
    return {
        "title": job.get("title"),
        "teaser": job.get("snippet") or None,
        "company": job.get("company"),
        "advertiser_id": job.get("companyIdEncrypted"),
        "classification": classification_name,
        "location": job.get("formattedLocation"),
        "work_type": _work_type(job),
        "work_arrangement": "Remote" if job.get("remoteLocation") else None,
        "salary_label": (job.get("salarySnippet") or {}).get("text"),
        "listing_date": _listing_date(job),
        "url": f"{BASE}/viewjob?jk={job['jobkey']}",
        "role_id": job.get("normTitle"),
        "display_type": job.get("packageTier"),
        "is_featured": bool(
            job.get("featuredEmployer") or job.get("featuredEmployerCandidate")
        ),
        "tags": _flatten_tags(job),
    }


# match the rendered banner, not the i18n string that's in every page bundle
def is_expired(html):
    return ">This job has expired" in html or 'data-testid="expiredJob"' in html


# None means body marker is missing - probably layout change
def parse_job_html(html, job):
    soup = BeautifulSoup(html, "lxml")
    body = soup.find(id="jobDescriptionText")
    if not body:
        return None
    meta = {
        "title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("formattedLocation"),
        "work_type": _work_type(job),
        "salary": (job.get("salarySnippet") or {}).get("text"),
        "rating": str(job.get("companyRating")) if job.get("companyRating") else None,
        "classifications": [classification_name, job.get("normTitle")],
        "url": f"{BASE}/viewjob?jk={job['jobkey']}",
    }
    md = markdownify.markdownify(str(body), heading_style="ATX").strip()
    return meta, md


async def load_search(tab, keyword, location):
    try:
        await asyncio.wait_for(
            tab.get(search_url(keyword, location)), timeout=NAV_TIMEOUT
        )
    except TimeoutError:
        return None
    # poll until cards render, riding out challenges that clear; the challenge
    # page swaps the DOM mid-query, which surfaces as ProtocolException
    for _ in range(8):
        try:
            if await tab.select_all("a.jcs-JobTitle", timeout=1.5):
                break
        except ProtocolException:
            await tab.sleep(1.5)
    html = await tab.get_content()
    if is_blocked(html):
        return None
    blob = _extract_mosaic_blob(html, "mosaic-provider-jobcards")
    if blob is None:
        return []
    mcm = (blob.get("metaData") or {}).get("mosaicProviderJobCardsModel") or {}
    return mcm.get("results") or []


# click the card and wait for the right pane to swap to its description
async def fetch_pane(tab, job_id):
    try:
        cards = await tab.select_all("a.jcs-JobTitle", timeout=3)
    except ProtocolException:
        return None
    card = next((c for c in cards if c.attrs.get("data-jk") == job_id), None)
    if card is None:
        return None
    await card.click()
    for _ in range(10):
        await tab.sleep(1)
        vjk = await tab.evaluate(
            "new URLSearchParams(location.search).get('vjk') || ''"
        )
        pane = await tab.evaluate(
            "(document.querySelector('.jobsearch-RightPane') || {}).outerHTML || ''"
        )
        if vjk == job_id and ("jobDescriptionText" in pane or is_expired(pane)):
            return pane
    # the pane may still show the previous job - saving it would corrupt this one
    return None


async def save_pane(job, pane):
    job_id = job["jobkey"]
    if is_expired(pane):
        mark_expired(db, SOURCE, job_id, pane)
        db.commit()
        return "expired"
    prev_hash, new_hash = upsert_job_html(db, SOURCE, job_id, pane)
    parsed = parse_job_html(pane, job)
    if parsed is not None:
        meta, markdown = parsed
        upsert_job_details(db, SOURCE, job_id, meta, markdown, new_hash)
        if prev_hash is not None and prev_hash != new_hash:
            log_history(
                db,
                SOURCE,
                job_id,
                "html_changed",
                html_hash=new_hash,
                markdown=markdown,
            )
    else:
        logging.error(f"{job_id} - saved pane but couldnt parse body")
    db.commit()
    return "added"


async def main():
    browser = await uc.start(
        headless=HEADLESS,
        browser_executable_path=CHROME_PATH,
        browser_args=BROWSER_ARGS,
    )
    tab = browser.main_tab

    have_html = {
        r[0]
        for r in db.execute(
            "SELECT id FROM jobs WHERE source = %s AND raw_html IS NOT NULL",
            (SOURCE,),
        ).fetchall()
    }

    seen = set()
    new_count = changed_count = relisted_count = 0
    added = expired = blocked = fetched = 0
    dropped = consecutive_blocks = 0

    offset = int(run_started_at.timestamp() // 60) % len(search_terms)
    terms = search_terms[offset:] + search_terms[:offset]

    try:
        for term in terms:
            if consecutive_blocks >= MAX_BLOCKS:
                logging.error(f"blocked {consecutive_blocks} in a row - stopping run")
                break
            for location in locations:
                results = await load_search(tab, term, location)
                await asyncio.sleep(search_delay)
                if results is None:
                    dropped += 1
                    consecutive_blocks += 1
                    logging.warning(f"{term} @ {location} - blocked")
                    break
                consecutive_blocks = 0

                want = []
                for job in results:
                    job_id = job.get("jobkey")
                    if not job_id or job_id in seen:
                        continue
                    seen.add(job_id)
                    event = upsert_job(
                        db, SOURCE, job_id, listing_fields(job), job, content_hash(job)
                    )
                    if event == "first_seen":
                        new_count += 1
                    elif event == "changed":
                        changed_count += 1
                    elif event == "relisted":
                        relisted_count += 1
                    if job_id not in have_html or event in ("changed", "relisted"):
                        want.append(job)
                db.commit()
                logging.info(f"{term} - {len(results)} listings, {len(want)} to fetch")

                for job in want:
                    if fetched >= limit:
                        break
                    fetched += 1
                    await asyncio.sleep(delay)
                    pane = await fetch_pane(tab, job["jobkey"])
                    if pane is None:
                        blocked += 1
                        logging.error(f"{job['jobkey']} - no pane")
                        continue
                    result = await save_pane(job, pane)
                    if result == "expired":
                        expired += 1
                        logging.info(f"{job['jobkey']} - expired")
                    else:
                        added += 1
                        logging.info(f"{job['jobkey']} - {job.get('title')}")

        logging.info(
            f"collected {len(seen)} listings - {new_count} new, "
            f"{changed_count} changed, {relisted_count} relisted"
        )

        if dropped or not seen:
            logging.warning(
                f"skipping delist sweep ({dropped} searches blocked, "
                f"{len(seen)} listings)"
            )
            delisted = 0
        else:
            delisted = sweep_delisted(db, SOURCE, run_started_at, DELIST_MISSES)
        purged = purge_stranded(db, SOURCE)
        db.commit()
    finally:
        browser.stop()

    db.close()

    logging.info(
        f"added {added} - expired {expired} - blocked {blocked} "
        f"- delisted {delisted} - purged {purged}"
    )


if __name__ == "__main__":
    logging.addLevelName(logging.WARNING, "WARN")
    logging.basicConfig(
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
    )
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    db = connect()
    start = time.time()
    run_started_at = datetime.now(UTC)
    uc.loop().run_until_complete(main())
    elapsed = int(time.time() - start)
    logging.info(f"completed in {elapsed // 60} m {elapsed % 60} s")
