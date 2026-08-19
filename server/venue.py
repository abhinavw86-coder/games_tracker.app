#!/usr/bin/env python3
"""Extract real venue addresses and registration details for AICF
tournaments from their prospectus PDFs.

AICF's all-events table lists only the host city, but each event's prospectus
(normally linked as a .pdf) contains "Venue: <address>", the last date of
entry, the entry fee and the prize fund. We download the PDF only for events
that survive the radius filter (a handful), convert it with pdftotext
(poppler-utils), and cache the result so daily rebuilds are cheap.

Chessfee events already carry their full venue in `location`, which we copy
into `venue` for a consistent schema.
"""

import json
import os
import re
import subprocess
from datetime import datetime

import requests

USER_AGENT = "Mozilla/5.0 (X11; Linux armv7l) TournamentTracker/1.0"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aicf_venue_cache.json")

# "Venue: <first line>" — requires a punctuation separator so the page heading
# "VENUE LOCATION" is not mistaken for a venue.
VENUE_RE = re.compile(r"\bvenue\s*[:.=]\s*([^\n]{3,})", re.IGNORECASE)

# Registration deadline, e.g. "Last Date of Entry : 10-08-2026". Also covers
# year-less forms like "Last date: August 14th" / "14th August" (the year is
# inferred from the tournament's start date).
DEADLINE_RE = re.compile(
    r"\b(?:last\s*date(?:\s*(?:of|for)\s*(?:entry|registration|receiving\s*entry))?"
    r"|registration\s*closes|closing\s*date|entry\s*closes|last\s*date|closes)\s*[:.=]?\s*"
    r"(?:([0-9]{1,2}\s*[-/.]\s*[0-9]{1,2}\s*[-/.]\s*[0-9]{2,4})"
    r"|([0-9]{1,2}(?:st|nd|rd|th)?\s*[A-Za-z]{3,9}\.?(?:\s*[0-9]{2,4})?)"
    r"|([A-Za-z]{3,9}\s*[0-9]{1,2}(?:st|nd|rd|th)?\.?(?:\s*[0-9]{2,4})?))",
    re.IGNORECASE,
)

# Entry fee, e.g. "Entry Fee : Rs. 1200", "Entry Fee: ₹1500" or
# "Regular Entry Fee : ₹1500". "Entry Fee Details:" must not match.
ENTRY_FEE_RE = re.compile(
    r"\b(?:entry|registration)\s*fee(?!\s*details)\s*[:.=]?\s*(?:rs\.?|inr|₹)?\s*"
    r"([0-9][0-9,]*)",
    re.IGNORECASE,
)

# Any rupee amount within a window after a prize keyword — catches both
# "Prize Fund : Rs. 1,00,000" and distribution-style pools ("1st ₹30,000 …").
CURRENCY_RE = re.compile(r"(?:rs\.?|inr|₹)\s*([0-9][0-9,]*)", re.IGNORECASE)
PRIZE_KEYWORD_RE = re.compile(
    r"\b(?:prize|prizes|prize pool|prize fund|total prize)\b", re.IGNORECASE,
)

DEADLINE_FORMATS = (
    "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%b %d %Y", "%B %d %Y",
)
COMPACT_DEADLINE_FORMATS = (
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%d-%b-%y",
)


def _strip_day_suffix(raw):
    return re.sub(r"(\d+)(st|nd|rd|th)", r"\1", raw, flags=re.IGNORECASE)


def parse_deadline(text, fallback_year=None, after=None):
    """Return an ISO date string, or None. `after` is the tournament start
    date (as ISO string) used to pick a sensible year for year-less dates:
    the deadline must be before the start, so a parsed date after it is
    shifted back one year."""
    match = DEADLINE_RE.search(text)
    if not match:
        return None
    raw = " ".join(filter(None, match.groups())).strip()
    raw = re.sub(r"\s+", " ", _strip_day_suffix(raw)).strip()
    if not raw:
        return None
    for fmt in DEADLINE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    compact = raw.replace(" ", "")
    for fmt in COMPACT_DEADLINE_FORMATS:
        try:
            return datetime.strptime(compact, fmt).date().isoformat()
        except ValueError:
            continue
    for fmt in ("%d %b", "%d %B", "%b %d", "%B %d"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
        if fallback_year is None:
            return None
        iso = parsed.replace(year=fallback_year).isoformat()
        if after and iso > after:
            iso = parsed.replace(year=fallback_year - 1).isoformat()
        return iso
    return None


def extract_prize(text):
    """Largest rupee amount near a prize keyword — handles labelled prize
    funds and distribution-style pools alike."""
    amounts = []
    for match in PRIZE_KEYWORD_RE.finditer(text):
        window = text[match.end():match.end() + 400]
        for am in CURRENCY_RE.finditer(window):
            amounts.append(_clean_number(am.group(1)))
    return max(amounts) if amounts else None

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


def _clean_number(raw):
    digits = re.sub(r"[^\d]", "", raw or "")
    return int(digits) if digits else None


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
    """Add venue / reg_deadline / entry_fee / prize_fund to one event dict."""
    if event.get("source") == "Chessfee":
        event["venue"] = event.get("location")
        return

    link = event.get("link") or ""
    if event.get("source") != "AICF" or not link.lower().endswith(".pdf"):
        event.pop("venue", None)
        event.pop("reg_deadline", None)
        event.pop("entry_fee", None)
        event.pop("prize_fund", None)
        return

    cache = load_cache()
    cached = cache.get(event["id"])
    if cached and cached.get("v") == 2 and cached.get("link") == link:
        venue = cached.get("venue")
        deadline = cached.get("reg_deadline")
        fee = cached.get("entry_fee")
        prize = cached.get("prize_fund")
    else:
        try:
            text = pdf_to_text(link)
            venue = extract_venue(text)
            deadline = parse_deadline(
                text,
                fallback_year=int(event.get("start_date", "")[:4]) or None,
                after=event.get("start_date"),
            )
            fee = _clean_number(ENTRY_FEE_RE.search(text).group(1)) if ENTRY_FEE_RE.search(text) else None
            prize = extract_prize(text)
        except Exception:
            venue = deadline = fee = prize = None
        cache[event["id"]] = {
            "v": 2,
            "link": link,
            "venue": venue,
            "reg_deadline": deadline,
            "entry_fee": fee,
            "prize_fund": prize,
        }
        save_cache(cache)

    for field, value in (("venue", venue), ("reg_deadline", deadline),
                         ("entry_fee", fee), ("prize_fund", prize)):
        if value:
            event[field] = value
        else:
            event.pop(field, None)


def enrich_all(events):
    for event in events:
        enrich(event)
