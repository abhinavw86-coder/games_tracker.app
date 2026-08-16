#!/usr/bin/env python3
"""Extract real venue addresses for AICF tournaments from their prospectus PDFs.

AICF's all-events table lists only the host city, but each event's prospectus
(normally linked as a .pdf) contains "Venue: <address>". We download the PDF
only for events that survive the radius filter (a handful), convert it with
pdftotext (poppler-utils), and cache the result so daily rebuilds are cheap.

Chessfee events already carry their full venue in `location`, which we copy
into `venue` for a consistent schema.
"""

import json
import os
import re
import subprocess

import requests

USER_AGENT = "Mozilla/5.0 (X11; Linux armv7l) TournamentTracker/1.0"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aicf_venue_cache.json")

# "Venue: <first line>" — requires a punctuation separator so the page heading
# "VENUE LOCATION" is not mistaken for a venue.
VENUE_RE = re.compile(r"\bvenue\s*[:.=]\s*([^\n]{3,})", re.IGNORECASE)

# Lines that end a venue address when they follow it.
NOISE = (
    "contact", "mobile", "tel:", "phone", "call ", "whatsapp", "entry ",
    "prize", "trophy", "qr code", "register", "organiz", "organis",
    "chief arbiter", "arbiter", "more details", "account", "a/c ",
    "bank ", "last date", "tie", "fee", "rupees", "rs.", "entry fee",
    "maps", "http", "goo.gl",
)


def load_cache():
    try:
        with open(CACHE_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as fh:
        json.dump(cache, fh, indent=2)


def pdf_to_text(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    proc = subprocess.run(
        ["pdftotext", "-", "-"], input=response.content,
        capture_output=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError("pdftotext failed")
    return proc.stdout.decode("utf-8", errors="replace")


def extract_venue(text):
    match = VENUE_RE.search(text)
    if not match:
        return None
    lines = [match.group(1).strip()]
    seen = False
    for line in text[match.end():].splitlines():
        line = line.strip().strip(" ,;:")
        if not line:
            if seen:
                break
            continue
        seen = True
        if any(k in line.lower() for k in NOISE):
            break
        if len(line) < 3:
            break
        lines.append(line)
        if len(lines) >= 4:
            break
    venue = re.sub(r"\s+", " ", ", ".join(lines)).strip(" ,;:-")
    return venue or None


def enrich(event):
    """Add a `venue` field to one event dict (in place)."""
    if event.get("source") == "Chessfee":
        event["venue"] = event.get("location")
        return

    link = event.get("link") or ""
    if event.get("source") != "AICF" or not link.lower().endswith(".pdf"):
        event.pop("venue", None)
        return

    cache = load_cache()
    cached = cache.get(event["id"])
    if cached and cached.get("link") == link:
        venue = cached.get("venue")
    else:
        try:
            venue = extract_venue(pdf_to_text(link))
        except Exception:
            venue = None
        cache[event["id"]] = {"link": link, "venue": venue}
        save_cache(cache)

    if venue:
        event["venue"] = venue
    else:
        event.pop("venue", None)


def enrich_all(events):
    for event in events:
        enrich(event)
