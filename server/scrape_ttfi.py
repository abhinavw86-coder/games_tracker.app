#!/usr/bin/env python3
"""Scrape upcoming table tennis events from the TTFI events page.

Source: https://www.ttfi.org/events
Output: list of dicts ready to be merged into tournaments.json.
"""

import argparse
import json
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

TTFI_URL = "https://www.ttfi.org/events"
USER_AGENT = "Mozilla/5.0 (X11; Linux armv7l) TournamentTracker/1.0"
TODAY = date.today()

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
MONTH_RE = "|".join(MONTHS)
_DATE_RE = re.compile(
    rf"(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:[-–—]\s*(\d{{1,2}})(?:st|nd|rd|th)?)?\s+({MONTH_RE}),?\s+(\d{{4}})",
    re.IGNORECASE,
)


def parse_date_range(text):
    """Parse '16th - 23rd August, 2026' or '7th March 2025' into (start, end)."""
    match = _DATE_RE.search(text or "")
    if not match:
        return None, None
    day1 = int(match.group(1))
    day2 = int(match.group(2)) if match.group(2) else day1
    month = MONTHS[match.group(3).lower()]
    year = int(match.group(4))
    try:
        start = date(year, month, day1)
        end = date(year, month, day2)
        if end < start:  # range crosses a month boundary, e.g. "27th - 02nd"
            end = date(year + 1, month, day2) if month == 12 else date(year, month + 1, day2)
        return start, end
    except ValueError:
        return None, None


def classify(title):
    low = title.lower()
    if "para" in low:
        category = "Para"
    elif "masters" in low:
        category = "Masters"
    elif "ranking" in low:
        category = "National Ranking"
    elif "khelo india" in low:
        category = "Khelo India"
    elif "championship" in low:
        category = "Championship"
    elif "commonwealth" in low:
        category = "Commonwealth"
    else:
        category = "Tournament"
    return category


def scrape():
    response = requests.get(TTFI_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    events = []
    for container in soup.find_all("div", class_="container"):
        banner = container.find("div", class_="banner_content")
        if not banner:
            continue

        title_el = banner.find("h2")
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)

        date_el = banner.find("h4")
        venue_el = banner.find("span", class_="vanue")
        date_text = date_el.get_text(" ", strip=True) if date_el else ""
        start, end = parse_date_range(date_text)
        if not start or end < TODAY:
            continue

        venue = venue_el.get_text(" ", strip=True) if venue_el else ""
        if venue.lower().startswith("venue:"):
            venue = venue[len("venue:"):].strip()

        organizer = ""
        para = banner.find("p")
        if para and "organized by" in para.get_text(" ", strip=True).lower():
            organizer = para.get_text(" ", strip=True).split(":", 1)[-1].strip()

        link = TTFI_URL
        anchor = container.find("a", href=lambda h: h and "/events/view/" in h)
        if anchor:
            link = anchor["href"] if anchor["href"].startswith("http") else f"https://www.ttfi.org{anchor['href']}"

        events.append(
            {
                "id": f"ttfi-{len(events) + 1}",
                "sport": "table_tennis",
                "name": title,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "location": venue or "India",
                "fide_rated": None,
                "time_control": None,
                "category": classify(title),
                "link": link,
                "source": "TTFI",
            }
        )
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape TTFI table tennis events")
    parser.add_argument("--output", help="write JSON to this file")
    args = parser.parse_args()
    events = scrape()
    if args.output:
        with open(args.output, "w") as fh:
            json.dump(events, fh, indent=2, ensure_ascii=False)
        print(f"Wrote {len(events)} table tennis events to {args.output}")
    else:
        print(json.dumps(events, indent=2, ensure_ascii=False))
