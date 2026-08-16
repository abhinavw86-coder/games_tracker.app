#!/usr/bin/env python3
"""Build tournaments.json: merge scraped events, geocode, compute distance
from home, add state + registration status, filter (radius or state/city),
enrich with venue details, and write the JSON the app reads.
"""

import argparse
import json
import math
import sys
from datetime import date, datetime, timezone, timedelta

from geocode import Geocoder
from scrape_chess import scrape as scrape_chess
from scrape_chessfee import scrape as scrape_chessfee
from venue import enrich_all

# Tournaments are filtered by distance from a home location. Set these to
# your own area before deploying (e.g. your city or suburb).
HOME = {"label": "Bengaluru, India", "lat": 12.9716, "lng": 77.5946}

# Only keep tournaments within this many km of home (used unless --state,
# --city or --no-radius is given).
RADIUS_KM = 35.0

IST = timezone(timedelta(hours=5, minutes=30))

# City -> state. AICF's all-events page only lists the host city.
CITY_STATE = {
    "agra": "Uttar Pradesh", "ahmedabad": "Gujarat", "ajmer": "Rajasthan",
    "amritsar": "Punjab", "aurangabad": "Maharashtra", "bangalore": "Karnataka",
    "bengaluru": "Karnataka",
    "bhopal": "Madhya Pradesh", "bhubaneswar": "Odisha", "bilaspur": "Chhattisgarh",
    "chandigarh": "Chandigarh", "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu",
    "dehradun": "Uttarakhand", "delhi": "Delhi", "new delhi": "Delhi",
    "dharwad": "Karnataka", "dindigul": "Tamil Nadu", "goa": "Goa",
    "guwahati": "Assam", "gwalior": "Madhya Pradesh", "hubballi": "Karnataka",
    "hyderabad": "Telangana", "indore": "Madhya Pradesh", "jaipur": "Rajasthan",
    "jammu": "Jammu and Kashmir", "jodhpur": "Rajasthan", "kanpur": "Uttar Pradesh",
    "kochi": "Kerala", "kolkata": "West Bengal", "kottayam": "Kerala",
    "kozhikode": "Kerala", "lucknow": "Uttar Pradesh", "madurai": "Tamil Nadu",
    "mangaluru": "Karnataka", "meerut": "Uttar Pradesh", "mumbai": "Maharashtra",
    "mysuru": "Karnataka", "mysore": "Karnataka", "nagpur": "Maharashtra",
    "nashik": "Maharashtra", "panaji": "Goa", "patna": "Bihar",
    "pune": "Maharashtra", "rajkot": "Gujarat", "ranchi": "Jharkhand",
    "salem": "Tamil Nadu", "shimla": "Himachal Pradesh", "srinagar": "Jammu and Kashmir",
    "surat": "Gujarat", "thane": "Maharashtra", "thiruvananthapuram": "Kerala",
    "tiruchirappalli": "Tamil Nadu", "trichy": "Tamil Nadu", "tirunelveli": "Tamil Nadu",
    "udaipur": "Rajasthan", "vadodara": "Gujarat", "varanasi": "Uttar Pradesh",
    "vijayawada": "Andhra Pradesh", "visakhapatnam": "Andhra Pradesh",
}


def state_of(location):
    if not location:
        return None
    low = location.strip().lower()
    if low in CITY_STATE:
        return CITY_STATE[low]
    for city, state in CITY_STATE.items():
        if city in low:
            return state
    return None


def event_status(event, today):
    deadline = event.get("reg_deadline")
    if not deadline:
        return None
    try:
        deadline_date = date.fromisoformat(deadline)
    except ValueError:
        return None
    days = (deadline_date - today).days
    if days < 0:
        return "closed"
    if days <= 7:
        return "closing soon"
    return "open"


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
    parser.add_argument("--state", help="keep only events in this state (ignores radius)")
    parser.add_argument("--city", help="keep only events in this city (ignores radius)")
    parser.add_argument("--no-radius", action="store_true", help="keep all geocodable events")
    args = parser.parse_args()

    print("Scraping chess (AICF) ...")
    events = scrape_chess()
    if not args.skip_chessfee:
        print("Scraping chess (Chessfee) ...")
        events += scrape_chessfee()

    for event in events:
        event["state"] = state_of(event.get("location"))

    geocoder = Geocoder()
    skipped = 0
    for event in events:
        coords = geocoder.lookup(event["location"])
        if not coords:
            skipped += 1
            continue
        event["lat"] = coords["lat"]
        event["lng"] = coords["lng"]
        event["distance_km"] = round(haversine_km(HOME["lat"], HOME["lng"], coords["lat"], coords["lng"]), 1)

    geocoded = [e for e in events if "distance_km" in e]
    if args.state:
        kept = [e for e in geocoded if e.get("state") == args.state]
        mode = f"state {args.state}"
    elif args.city:
        kept = [e for e in geocoded if (e.get("location") or "").lower() == args.city.lower()]
        mode = f"city {args.city}"
    elif args.no_radius:
        kept = geocoded
        mode = "all states"
    else:
        kept = [e for e in geocoded if e["distance_km"] <= RADIUS_KM]
        mode = f"{RADIUS_KM} km of {HOME['label']}"

    kept.sort(key=lambda e: (e["start_date"], e["distance_km"]))

    print(f"Enriching {len(kept)} events with venue details (prospectus PDFs) ...")
    enrich_all(kept)

    today = date.today()
    for event in kept:
        status = event_status(event, today)
        if status:
            event["event_status"] = status
        else:
            event.pop("event_status", None)

    payload = {
        "generated_at": datetime.now(IST).isoformat(timespec="seconds"),
        "home": HOME,
        "radius_km": RADIUS_KM,
        "tournaments": kept,
    }

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print(f"\n{len(kept)} tournaments within {mode} "
          f"({skipped} events had no geocodable location)")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    sys.exit(main())
