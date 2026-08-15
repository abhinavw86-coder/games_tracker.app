#!/usr/bin/env python3
"""Geocode Indian city names to lat/lng using OpenStreetMap Nominatim.

Results are cached on disk so we only hit the public API once per city.
"""

import json
import os
import time

import requests

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".geocode_cache.json")
USER_AGENT = "TournamentTracker-Pi/1.0"
MIN_INTERVAL = 1.1


class Geocoder:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        self.cache = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as fh:
                    self.cache = json.load(fh)
            except (ValueError, OSError):
                self.cache = {}
        self._last_request = 0.0

    def lookup(self, place):
        key = " ".join((place or "").strip().split()).lower()
        if not key:
            return None
        if key in self.cache:
            return self.cache[key]

        # Nominatim asks for no more than ~1 request/second
        wait = MIN_INTERVAL - (time.time() - self._last_request)
        if wait > 0:
            time.sleep(wait)

        result = None
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": f"{place}, India", "format": "json", "limit": 1},
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            if data:
                result = {
                    "lat": round(float(data[0]["lat"]), 5),
                    "lng": round(float(data[0]["lon"]), 5),
                }
        except Exception:
            result = None
        finally:
            self._last_request = time.time()

        self.cache[key] = result
        self._save()
        return result

    def _save(self):
        try:
            with open(self.cache_file, "w") as fh:
                json.dump(self.cache, fh, indent=2)
        except OSError:
            pass
