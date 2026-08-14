# Tournament Tracker (tracker.app)

A macOS app for your brother that lists upcoming **chess** and **table tennis**
tournaments near **Sarjapur, Bengaluru**. A Raspberry Pi scrapes the tournaments
from two sites and serves them as JSON over nginx; the Mac app polls that JSON
and shows everything: date, sport, location, distance, FIDE / non-FIDE, and time
control (classical / rapid / blitz / bullet).

```
AICF (chess) ──┐
               ├─► server/build_json.py ─► tournaments.json ─► nginx ─► tracker.app (macOS 12+)
TTFI (table tennis) ─┘
```

- Chess source: **AICF All-Events** — `https://aicf.in/all-events/`
- Table tennis source: **TTFI Events** — `https://www.ttfi.org/events`
- Home is hardcoded to **Sarjapur, Bengaluru** (12.8620, 77.7860) with a 200 km radius
  (change `HOME` / `RADIUS_KM` at the top of `server/build_json.py`).

## Layout

```
server/                  Raspberry Pi side
  scrape_chess.py        AICF chess scraper
  scrape_ttfi.py         TTFI table tennis scraper
  build_json.py          merge + geocode + distance filter → tournaments.json
  geocode.py             OpenStreetMap Nominatim geocoder (cached)
  nginx.conf             nginx site config for the JSON feed
  install_nginx.sh       one-shot Pi setup (pkexec, apt)
tracker/app.py           macOS Tkinter app (stdlib only)
run.py                   app entry point
sample.json              fake feed for testing without the Pi
scripts/build_macos.sh   PyInstaller → .app → .dmg
.github/workflows/build-macos.yml   free macOS build via GitHub Actions
```

## 1. Set up the Raspberry Pi (one time)

Run on the Pi (it will prompt for your password via `pkexec`):

```bash
chmod +x install_nginx.sh
./install_nginx.sh
```

This installs nginx, copies the server to `/opt/tracker`, builds the feed into
`/var/www/tracker/tournaments.json`, reloads nginx, and schedules a nightly
refresh at 05:00 via cron.

Note the printed URL, e.g. `http://192.168.1.50/tournaments.json` (or
`http://raspberrypi.local/tournaments.json` if your router does mDNS).

### Is nginx the best webserver?

Yes, for this job: a tiny static file served once a day. Alternatives: **Caddy**
(automatic HTTPS, single binary — nicer if you ever want it public), **lighttpd**
(even lighter), Python's `http.server` (dev only — do not use on a real Pi).

### Rebuild the feed by hand (e.g. to test)

```bash
cd /opt/tracker
.venv/bin/python build_json.py --output /var/www/tracker/tournaments.json
```

The first run geocodes every city via OpenStreetMap (≈1 req/s, takes a few
minutes). Results are cached in `server/.geocode_cache.json`, so later runs are
fast and offline. Cities that can't be geocoded are skipped.

## 2. Build the Mac app (.dmg)

### Easiest: free GitHub Actions build

1. Push this folder to a GitHub repo (it must include the `.github/workflows` folder).
2. Go to **Actions → Build macOS DMG → Run workflow**, or push a tag `git tag v1.0.0 && git push --tags`.
3. Download **tracker-dmg** from the run's Artifacts. It contains `tracker-1.0.0-macos.dmg`.

The workflow runs on an **Intel macOS 13** runner, so the app runs natively on
macOS 12 Intel Macs and via Rosetta 2 on Apple Silicon.

### Or build on a Mac

```bash
brew install python@3.12   # or use any Python 3.8+
./scripts/build_macos.sh 1.0.0   # needs Xcode CLT for PyInstaller
```

## 3. Install and use tracker.app

1. Open the DMG, drag `tracker.app` into **Applications**.
2. Right-click → Open the first time (it's not signed, so Gatekeeper will warn).
3. Enter the Pi's URL in the **Server URL** box and press **Refresh**.
4. Filter by **Sport**, **FIDE**, **Time control**, and **Sort by** date or distance.
   Double-click any row for full details (dates, distance, source, link).
5. "Load sample" shows built-in example data so you can try it before the Pi is up.

The URL is remembered between launches.

## JSON schema (what the Pi serves)

```json
{
  "generated_at": "2026-08-14T21:00:00+05:30",
  "home": { "label": "Sarjapur, Bengaluru", "lat": 12.862, "lng": 77.786 },
  "radius_km": 200.0,
  "tournaments": [
    {
      "id": "aicf-479936",
      "sport": "chess",                 // "chess" | "table_tennis"
      "name": "6th Check n Mate All India Open FIDE Rated Rapid Chess Tournament",
      "start_date": "2026-08-15",
      "end_date": "2026-08-15",
      "location": "Bengaluru",
      "distance_km": 24.8,
      "fide_rated": true,                // chess: true/false, table tennis: null
      "time_control": "rapid",           // chess: classical/rapid/blitz/bullet, tt: null
      "category": "Open",
      "link": "https://aicf.in/all-events/",
      "source": "AICF"
    }
  ]
}
```

## Troubleshooting

- **App says it can't reach the Pi**: try the Pi's raw IP instead of
  `raspberrypi.local` (many routers don't support mDNS), and check nginx on the
  Pi with `systemctl status nginx`.
- **No table tennis events**: TTFI's page only lists a handful of upcoming events
  with dates; that's normal.
- **AICF table has typos**: the scraper auto-corrects swapped/typo dates
  (see `normalize_dates` in `server/scrape_chess.py`).
- **App won't open on macOS**: it's unsigned — right-click → Open → Open.
