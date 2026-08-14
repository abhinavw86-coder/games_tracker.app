"""Tournament Tracker — shows chess & table-tennis tournaments served by the
Raspberry Pi (nginx). Uses only the Python standard library so it bundles
cleanly with PyInstaller."""

import json
import os
import platform
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.error import URLError
from urllib.request import urlopen

APP_NAME = "Tournament Tracker"
DEFAULT_URL = "http://raspberrypi.local/tournaments.json"
SPORTS = {"chess": "Chess", "table_tennis": "Table Tennis"}
TIME_CONTROLS = ["classical", "rapid", "blitz", "bullet"]
FILTER_SORTS = {"Start date": "start_date", "Distance": "distance_km"}


def config_dir():
    if platform.system() == "Darwin":
        base = os.path.expanduser("~/Library/Application Support/tracker.app")
    else:
        base = os.path.expanduser("~/.config/tracker")
    os.makedirs(base, exist_ok=True)
    return base


def load_config():
    path = os.path.join(config_dir(), "config.json")
    try:
        with open(path, "r") as fh:
            data = json.load(fh)
            return str(data.get("url", DEFAULT_URL))
    except (OSError, ValueError):
        return DEFAULT_URL


def save_config(url):
    path = os.path.join(config_dir(), "config.json")
    try:
        with open(path, "w") as fh:
            json.dump({"url": url}, fh)
    except OSError:
        pass


def fetch_feed(url):
    with urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def format_date(date_text):
    if not date_text:
        return "?"
    try:
        parts = date_text.split("-")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{day:02d}-{month:02d}-{year}"
    except (ValueError, IndexError):
        return date_text


class TrackerApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        root.geometry("980x560")
        root.minsize(760, 420)

        self.url_var = tk.StringVar(value=load_config())
        self.sport_var = tk.StringVar(value="All")
        self.fide_var = tk.StringVar(value="All")
        self.tc_var = tk.StringVar(value="All")
        self.sort_var = tk.StringVar(value="Start date")
        self.status_var = tk.StringVar(value="Enter the Pi's URL and press Refresh")
        self.raw_tournaments = []
        self.feed_meta = {}

        self._build_toolbar()
        self._build_table()
        self._build_statusbar()

        for var in (self.sport_var, self.fide_var, self.tc_var, self.sort_var):
            var.trace_add("write", self._on_filter_change)

    def _on_filter_change(self, *_args):
        self.refresh_view()

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(10, 8))
        bar.pack(fill="x")

        ttk.Label(bar, text="Server URL").pack(side="left")
        entry = ttk.Entry(bar, textvariable=self.url_var, width=44)
        entry.pack(side="left", padx=(6, 6))

        ttk.Button(bar, text="Refresh", command=self.refresh_feed).pack(side="left")
        ttk.Button(bar, text="Load sample", command=self.load_sample).pack(side="left", padx=(6, 0))

        filters = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        filters.pack(fill="x")
        self._filter_row(
            filters, "Sport", self.sport_var,
            ["All", "Chess", "Table Tennis"],
        )
        self._filter_row(
            filters, "FIDE", self.fide_var,
            ["All", "FIDE", "Non-FIDE"],
        )
        self._filter_row(
            filters, "Time control", self.tc_var,
            ["All"] + [tc.capitalize() for tc in TIME_CONTROLS],
        )
        self._filter_row(
            filters, "Sort by", self.sort_var,
            list(FILTER_SORTS),
        )

    def _filter_row(self, parent, label, variable, options):
        ttk.Label(parent, text=label).pack(side="left", padx=(14, 4))
        combo = ttk.Combobox(parent, textvariable=variable, values=options,
                             state="readonly", width=12)
        combo.pack(side="left")

    def _build_table(self):
        columns = ("date", "sport", "name", "location", "dist", "fide", "tc", "category")
        headings = {
            "date": "Start",
            "sport": "Sport",
            "name": "Tournament",
            "location": "Location",
            "dist": "Dist",
            "fide": "FIDE",
            "tc": "Time Control",
            "category": "Type",
        }
        wrap = tk.Frame(self.root)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self.table = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self.table.heading(col, text=headings[col])
        self.table.column("date", width=80, anchor="center")
        self.table.column("sport", width=100)
        self.table.column("name", width=320)
        self.table.column("location", width=150)
        self.table.column("dist", width=60, anchor="center")
        self.table.column("fide", width=50, anchor="center")
        self.table.column("tc", width=80, anchor="center")
        self.table.column("category", width=110)

        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.table.bind("<Double-1>", self.show_details)

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, padding=(10, 4))
        bar.pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status_var, anchor="w").pack(side="left")

    def refresh_feed(self):
        url = self.url_var.get().strip() or DEFAULT_URL
        save_config(url)
        self.status_var.set(f"Fetching {url} ...")
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url):
        try:
            data = fetch_feed(url)
        except Exception as exc:
            self.root.after(0, lambda: self._fetch_failed(exc))
            return
        self.root.after(0, lambda: self._feed_loaded(data))

    def _fetch_failed(self, error):
        self.status_var.set(f"Could not reach the Pi: {error}")
        messagebox.showerror(APP_NAME, f"Could not fetch tournaments:\n{error}\n\n"
                             f"Check the server URL and that the Pi is on and nginx is running.")

    def _feed_loaded(self, data):
        self.raw_tournaments = data.get("tournaments", [])
        self.feed_meta = data
        home = data.get("home", {})
        when = data.get("generated_at", "").replace("T", " ")[:16]
        where = f"near {home.get('label', 'home')}" if home else ""
        self.status_var.set(
            f"{len(self.raw_tournaments)} tournaments {where} · feed updated {when}"
        )
        self.refresh_view()

    def load_sample(self):
        sample_path = self._sample_path()
        try:
            with open(sample_path, "r") as fh:
                data = json.load(fh)
        except OSError as exc:
            self.status_var.set("Sample data not found")
            messagebox.showerror(APP_NAME, f"Could not load sample data:\n{exc}")
            return
        self._feed_loaded(data)
        self.status_var.set(
            f"Showing sample data ({len(data.get('tournaments', []))} tournaments) — "
            "press Refresh to fetch from the Pi"
        )

    def _sample_path(self):
        if getattr(sys, "_MEIPASS", None):
            return os.path.join(sys._MEIPASS, "sample.json")
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample.json")

    def refresh_view(self):
        for item in self.table.get_children():
            self.table.delete(item)

        sport = self.sport_var.get()
        fide = self.fide_var.get()
        tc = self.tc_var.get().lower()
        sort_key = FILTER_SORTS.get(self.sort_var.get(), "start_date")

        rows = []
        for t in self.raw_tournaments:
            sport_id = t.get("sport", "")
            if sport != "All" and sport != SPORTS.get(sport_id, sport_id):
                continue
            if sport_id == "chess":
                if fide == "FIDE" and not t.get("fide_rated"):
                    continue
                if fide == "Non-FIDE" and t.get("fide_rated"):
                    continue
                if tc != "all" and (t.get("time_control") or "classical").lower() != tc:
                    continue

            start = t.get("start_date", "") or "9999-99-99"
            dist = t.get("distance_km")
            dist = dist if isinstance(dist, (int, float)) else float("inf")
            rows.append((start, dist, t))

        if sort_key == "distance_km":
            rows.sort(key=lambda r: (r[1], r[0]))
        else:
            rows.sort(key=lambda r: (r[0], r[1]))

        for _, _, t in rows:
            fide_text = "Yes" if t.get("fide_rated") is True else ("No" if t.get("fide_rated") is False else "—")
            tc_text = (t.get("time_control") or "—").capitalize() if t.get("sport") == "chess" else "—"
            dist = t.get("distance_km")
            dist_text = f"{dist:.0f} km" if isinstance(dist, (int, float)) else "—"
            self.table.insert(
                "", "end",
                values=(
                    format_date(t.get("start_date")),
                    SPORTS.get(t.get("sport", ""), t.get("sport", "?")),
                    t.get("name", "?"),
                    t.get("location", "?"),
                    dist_text,
                    fide_text,
                    tc_text,
                    t.get("category", "—"),
                ),
                tags=(str(id(t)),),
            )

    def show_details(self, _event=None):
        selected = self.table.selection()
        if not selected:
            return
        item = self.table.item(selected[0])
        tag = item["tags"][0] if item["tags"] else ""
        match = [t for t in self.raw_tournaments if str(id(t)) == tag]
        if not match:
            return
        t = match[0]
        details = (
            f"{t.get('name', '?')}\n\n"
            f"Sport:        {SPORTS.get(t.get('sport', ''), '?')}\n"
            f"Dates:        {t.get('start_date')} → {t.get('end_date') or 'TBC'}\n"
            f"Location:     {t.get('location', '?')}\n"
            f"Distance:     {t.get('distance_km')} km from Sarjapur, Bengaluru\n"
            f"FIDE rated:   {t.get('fide_rated')}\n"
            f"Time control: {t.get('time_control')}\n"
            f"Type:         {t.get('category')}\n"
            f"Source:       {t.get('source')}\n"
            f"Link:         {t.get('link')}"
        )
        messagebox.showinfo(APP_NAME, details)


def main():
    root = tk.Tk()
    app = TrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
