#!/usr/bin/env python3
"""Scrape upcoming chess tournaments from Chessfee (a registration portal).

Source: https://www.chessfee.com/tournament_ongoing.php (paginated list of
upcoming tournaments). The listing truncates venue addresses, so each event's
detail page is fetched once and cached in .chessfee_cache.json to recover the
full address.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

BASE = "https://www.chessfee.com/"
LIST_URL = BASE + "tournament_ongoing.php"
DETAIL_URL = BASE + "tmt_details.php?id={}"
USER_AGENT = "Mozilla/5.0 (X11; Linux armv7l) TournamentTracker/1.0"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chessfee_cache.json")
TODAY = date.today()
MAX_PAGES = 20


def parse_date(text):
    for fmt in ("%d %B %Y", "%d %b %Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_range(text):
    """Parse '16 August 2026 to 16 August 2026' into (start, end) dates."""
    text = text.strip()
    match = re.match(r"(.+?)\s*(?:to|-)\s*(.+)", text)
    if match:
        a, b = parse_date(match.group(1)), parse_date(match.group(2))
        if a and b:
            return min(a, b), max(a, b)
    return parse_date(text), None


def classify(name):
    """Derive time control + category from the tournament name."""
    low = name.lower()
    time_control = "classical"
    for keyword, value in (("bullet", "bullet"), ("blitz", "blitz"), ("rapid", "rapid")):
        if keyword in low:
            time_control = value
            break

    if "championship" in low:
        category = "Championship"
    elif "open" in low:
        category = "Open"
    elif "team" in low:
        category = "Team"
    elif time_control != "classical":
        category = time_control.title()
    else:
        category = "Tournament"
    return time_control, category


def fetch_soup(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def load_cache():
    try:
        with open(CACHE_FILE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as fh:
        json.dump(cache, fh, indent=2)


def event_id(href):
    match = re.search(r"id=(\d+)", href or "")
    return match.group(1) if match else None


def parse_venue(soup):
    """Full venue from the detail page: '<b>Venue</b> : <address>'."""
    for paragraph in soup.find_all("p"):
        label = paragraph.find("b")
        if label and "venue" in label.get_text().lower():
            return paragraph.get_text(" ", strip=True).split(":", 1)[-1].strip()
    return None


def scrape():
    cache = load_cache()
    events = []
    seen = set()

    for page in range(1, MAX_PAGES + 1):
        url = f"{LIST_URL}?page={page}" if page > 1 else LIST_URL
        try:
            soup = fetch_soup(url)
        except requests.RequestException:
            break

        articles = [a for a in soup.find_all("article")
                    if a.find("a", href=re.compile(r"tmt_details\.php\?id=\d+"))]
        if not articles:
            break

        for art in articles:
            detail_a = art.find("a", href=re.compile(r"tmt_details\.php\?id=\d+"))
            eid = event_id(detail_a["href"])
            if not eid or eid in seen:
                continue
            seen.add(eid)

            h5 = art.find("h5")
            name = h5.get_text(" ", strip=True) if h5 else ""
            if "test" in name.lower():
                continue
            date_tag = art.find("b")
            start, end = parse_range(date_tag.get_text(" ", strip=True)) if date_tag else (None, None)
            if not start or start < TODAY:
                continue

            venue_short = ""
            for li in art.find_all("li"):
                if "justify" in (li.get("style") or ""):
                    venue_short = li.get_text(" ", strip=True)
                    break

            venue = (cache.get(eid) or {}).get("venue")
            if not venue:
                try:
                    venue = parse_venue(fetch_soup(DETAIL_URL.format(eid))) or venue_short
                    cache[eid] = {"venue": venue, "name": name}
                    time.sleep(0.4)
                except requests.RequestException:
                    venue = venue_short

            time_control, category = classify(name)
            events.append(
                {
                    "id": f"chessfee-{eid}",
                    "sport": "chess",
                    "name": name,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat() if end else None,
                    "location": venue or venue_short,
                    "fide_rated": "fide" in name.lower(),
                    "time_control": time_control,
                    "category": category,
                    "link": f"{BASE}tmt_details.php?id={eid}",
                    "source": "Chessfee",
                }
            )
        time.sleep(0.4)

    save_cache(cache)
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Chessfee chess events")
    parser.add_argument("--output", help="write JSON to this file")
    args = parser.parse_args()
    events = scrape()
    if args.output:
        with open(args.output, "w") as fh:
            json.dump(events, fh, indent=2, ensure_ascii=False)
        print(f"Wrote {len(events)} chessfee events to {args.output}")
    else:
        print(json.dumps(events, indent=2, ensure_ascii=False))
