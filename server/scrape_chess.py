#!/usr/bin/env python3
"""Scrape upcoming chess tournaments from the AICF All-Events page.

Source: https://aicf.in/all-events/
Output: list of dicts ready to be merged into tournaments.json.
"""

import argparse
import json
import sys
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

AICF_URL = "https://aicf.in/all-events/"
USER_AGENT = "Mozilla/5.0 (X11; Linux armv7l) TournamentTracker/1.0"
TODAY = date.today()


def parse_date(text):
    for fmt in ("%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def normalize_dates(start, end):
    """AICF's table occasionally has swapped or typo'd dates. Clean them up."""
    if start is None:
        return None, None
    if end is None:
        end = start
    if end < start:
        start, end = end, start
    if (end - start).days > 90:
        # Likely a year typo in the source; keep the start date, drop the end.
        return start, None
    return start, end


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


def scrape():
    response = requests.get(AICF_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    table = soup.find("table")
    if not table:
        raise RuntimeError("AICF: no table found on page")

    events = []
    for row in table.find_all("tr")[1:]:
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        if len(cells) < 5 or not cells[0]:
            continue

        name, code, start_text, end_text, place = cells[:5]
        start = parse_date(start_text) or parse_date(end_text)
        end = parse_date(end_text) or start
        if not start or start < TODAY:
            continue
        start, end = normalize_dates(start, end)
        if start < TODAY:
            continue
        end_text = end.isoformat() if end else None

        time_control, category = classify(name)
        link = AICF_URL
        anchor = row.find("a", href=True)
        if anchor and anchor["href"]:
            link = anchor["href"] if anchor["href"].startswith("http") else AICF_URL

        events.append(
            {
                "id": f"aicf-{code}",
                "sport": "chess",
                "name": name,
            "start_date": start.isoformat(),
            "end_date": end_text,
                "location": place,
                "fide_rated": "fide" in name.lower(),
                "time_control": time_control,
                "category": category,
                "link": link,
                "source": "AICF",
            }
        )
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape AICF chess events")
    parser.add_argument("--output", help="write JSON to this file")
    args = parser.parse_args()
    events = scrape()
    if args.output:
        with open(args.output, "w") as fh:
            json.dump(events, fh, indent=2, ensure_ascii=False)
        print(f"Wrote {len(events)} chess events to {args.output}")
    else:
        print(json.dumps(events, indent=2, ensure_ascii=False))
