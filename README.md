# Tournament Tracker

A macOS app that lists upcoming **chess** tournaments near a chosen location.
A Raspberry Pi scrapes tournaments from two public sources and serves them as
JSON over nginx; the app fetches that JSON and shows everything: date, venue,
distance, FIDE / non-FIDE status, and time control (classical / rapid /
blitz / bullet).

```
AICF (all-India official) ──┐
                            ├─► server/build_json.py ─► tournaments.json ─► nginx ─► tracker.app (macOS 12+)
Chessfee (registration portal) ─┘
```

- Chess source 1: **AICF All-Events** — `https://aicf.in/all-events/`
  (official, FIDE-rated events)
- Chess source 2: **Chessfee** — `https://www.chessfee.com/tournament_ongoing.php`
  (casual opens and children's tournaments, FIDE and non-FIDE)
- Home location and search radius are constants in `server/build_json.py`
  (defaults to Bengaluru, India with a 35 km radius).

## Layout

```
server/                  Raspberry Pi side
  scrape_chess.py        AICF chess scraper
  scrape_chessfee.py     Chessfee chess scraper (casual/children's events)
  build_json.py          merge + geocode + distance filter → tournaments.json
  geocode.py             OpenStreetMap Nominatim geocoder (cached)
  nginx.conf             nginx site config for the JSON feed
  tracker.service        systemd unit: builds the feed (runs on boot)
  tracker.timer          systemd timer: daily refresh at 05:00
  install_nginx.sh       one-shot Pi setup (pkexec, apt)
tracker/app.py           macOS Tkinter app (stdlib only)
run.py                   app entry point
sample.json              example feed for testing without the Pi
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
`/var/www/tracker/tournaments.json`, reloads nginx, and sets up a **systemd
timer** that runs the feed build at boot and every day at 05:00.

Note the printed URL, e.g. `http://192.168.1.50/tournaments.json` (or a
`*.local` hostname if your router does mDNS).

### Why nginx?

This serves one small JSON file once a day, so any static webserver works.
nginx is fast and tiny. Alternatives: **Caddy** (automatic HTTPS), **lighttpd**
(even lighter), Python's `http.server` (dev only).

### Rebuild the feed by hand

```bash
cd /opt/tracker
.venv/bin/python build_json.py --output /var/www/tracker/tournaments.json
```

The first run geocodes every city via OpenStreetMap (≈1 req/s, takes a few
minutes). Results are cached in `server/.geocode_cache.json`, so later runs are
fast and offline. Cities that can't be geocoded are skipped.

### Configure the home location

Edit `HOME` in `server/build_json.py` — it needs `label`, `lat`, and `lng`.
Tournaments farther than `RADIUS_KM` from it are filtered out.

## 2. Build the Mac app (.dmg)

### Free GitHub Actions build

1. Push this repository to GitHub (must include the `.github/workflows` folder).
2. Go to **Actions → Build macOS DMG → Run workflow**, or push a tag (`git tag v1.0.0 && git push --tags`).
3. Download the **tracker-dmg** artifact from the run. It contains `tracker-1.0.0-macos.dmg`.

The workflow runs on an **Intel macOS 15 runner** (`macos-15-intel`), so the app
is x86_64: native on Intel Macs (including macOS 12) and runs on Apple Silicon
via Rosetta 2.

### Or build on a Mac

```bash
./scripts/build_macos.sh 1.0.0   # needs Python 3.8+ and PyInstaller
```

## 3. Install and use tracker.app

1. Open the DMG, drag `tracker.app` into **Applications**.
2. Right-click → Open the first time (it's unsigned, so Gatekeeper will warn).
3. Enter the Pi's URL in the **Server URL** box and press **Refresh**.
4. Filter by **Sport**, **FIDE**, **Time control**, and **Sort by** date or distance.
   Double-click any row for full details (dates, distance, source, link).
5. "Load sample" shows bundled example data so you can try it before the Pi is up.

The URL is remembered between launches.

## JSON schema (what the Pi serves)

```json
{
  "generated_at": "2026-08-15T05:00:00+05:30",
  "home": { "label": "Bengaluru, India", "lat": 12.9716, "lng": 77.5946 },
  "radius_km": 35.0,
  "tournaments": [
    {
      "id": "aicf-479936",
      "sport": "chess",
      "name": "6th Check n Mate All India Open FIDE Rated Rapid Chess Tournament",
      "start_date": "2026-08-15",
      "end_date": "2026-08-15",
      "location": "Bengaluru",
      "distance_km": 24.8,
      "fide_rated": true,
      "time_control": "rapid",           // classical | rapid | blitz | bullet
      "category": "Open",
      "link": "https://aicf.in/all-events/",
      "source": "AICF"                    // "AICF" | "Chessfee"
    }
  ]
}
```

## Troubleshooting

- **App says it can't reach the Pi**: try the Pi's raw IP instead of the
  `*.local` hostname (many routers don't support mDNS), and check nginx on the
  Pi with `systemctl status nginx`.
- **No tournaments near me**: the 35 km radius filters out everything farther
  away. Raise `RADIUS_KM` in `server/build_json.py` (e.g. 60) to widen it.
- **Chessfee list is empty some weeks**: it's driven by what organizers publish;
  most of its events are in Tamil Nadu, so Bangalore ones appear intermittently.
- **AICF table has typos**: the scraper auto-corrects swapped/typo dates
  (see `normalize_dates` in `server/scrape_chess.py`).
- **App won't open on macOS**: it's unsigned — right-click → Open → Open.
