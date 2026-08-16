#!/usr/bin/env python3
"""Build tournaments.json: merge scraped events, geocode, compute distance
from home, filter by radius, and write the JSON the Mac app reads.
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone, timedelta

from geocode import Geocoder
from scrape_chess import scrape as scrape_chess
from scrape_chessfee import scrape as scrape_chessfee
from venue import enrich_all

# Tournaments are filtered by distance from a home location. Set these to
# your own area before deploying (e.g. your city or suburb).
HOME = {"label": "Bengaluru, India", "lat": 12.9716, "lng": 77.5946}

# Only keep tournaments within this many km of home.
RADIUS_KM = 35.0

IST = timezone(timedelta(hours=5, minutes=30))


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def main():
    parser = argparse.ArgumentParser(description="Build tournaments.json")
    parser.add_argument("--output", default="tournaments.json", help="output file (default: tournaments.json)")
    parser.add_argument("--skip-chessfee", action="store_true", help="skip the Chessfee scrape")
    args = parser.parse_args()

    print("Scraping chess (AICF) ...")
    events = scrape_chess()
    if not args.skip_chessfee:
        print("Scraping chess (Chessfee) ...")
        events += scrape_chessfee()

    geocoder = Geocoder()
    kept = 0
    skipped = 0
    for event in events:
        coords = geocoder.lookup(event["location"])
        if not coords:
            skipped += 1
            continue
        event["lat"] = coords["lat"]
        event["lng"] = coords["lng"]
        event["distance_km"] = round(haversine_km(HOME["lat"], HOME["lng"], coords["lat"], coords["lng"]), 1)
        if event["distance_km"] <= RADIUS_KM:
            kept += 1

    events = [e for e in events if "distance_km" in e and e["distance_km"] <= RADIUS_KM]
    events.sort(key=lambda e: (e["start_date"], e["distance_km"]))

    print(f"Enriching {len(events)} in-radius events with venue addresses (prospectus PDFs) ...")
    enrich_all(events)

    payload = {
        "generated_at": datetime.now(IST).isoformat(timespec="seconds"),
        "home": HOME,
        "radius_km": RADIUS_KM,
        "tournaments": events,
    }

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"\n{len(events)} tournaments within {RADIUS_KM} km of {HOME['label']} "
          f"({skipped} events had no geocodable location)")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    sys.exit(main())
