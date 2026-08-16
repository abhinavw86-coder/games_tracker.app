"""Tournament Tracker — shows chess tournaments served by the Raspberry Pi
(nginx). Uses only the Python standard library so it bundles cleanly with
PyInstaller."""

import json
import os
import platform
import re
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

APP_NAME = "Tournament Tracker"
DEFAULT_URL = "http://pi-bookworm.local/tournaments.json"
TIME_CONTROLS = ["classical", "rapid", "blitz", "bullet"]
FILTER_SORTS = {"Start date": "start_date", "Distance": "distance_km"}
U10_RE = re.compile(r"\bu\s?[-–]?\s?10\b|\bunder\s?[-–]?\s?10\b", re.IGNORECASE)

BG = "#eef1f5"
SURFACE = "#ffffff"
BORDER = "#d9dee6"
TEXT = "#1f2937"
MUTED = "#6b7280"
ACCENT = "#2563eb"
ACCENT_DARK = "#1d4ed8"
ACCENT_SOFT = "#dbeafe"
HEADER_BG = "#f3f5f8"
ROW_ODD = "#ffffff"
ROW_EVEN = "#f2f6fb"
FONT = "Helvetica"


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


def is_u10(tournament):
    return bool(U10_RE.search(tournament.get("name") or ""))


def maps_url(location):
    return "https://www.google.com/maps/search/?api=1&query=" + quote(location)


def apply_style(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", font=(FONT, 10), background=BG, foreground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("Bar.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Bar.TLabel", background=SURFACE, foreground=MUTED)
    style.configure("Title.TLabel", background=SURFACE, foreground=TEXT,
                    font=(FONT, 17, "bold"))
    style.configure("Sub.TLabel", background=SURFACE, foreground=MUTED,
                    font=(FONT, 10))
    style.configure("Status.TLabel", background=SURFACE, foreground=MUTED)

    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                    font=(FONT, 10, "bold"), padding=(18, 8), borderwidth=0,
                    focuscolor=ACCENT)
    style.map("Accent.TButton",
              background=[("active", ACCENT_DARK), ("pressed", ACCENT_DARK),
                          ("disabled", MUTED)])
    style.configure("Soft.TButton", background=SURFACE, foreground=TEXT,
                    font=(FONT, 10), padding=(14, 8), borderwidth=1,
                    bordercolor=BORDER, focuscolor=SURFACE)
    style.map("Soft.TButton",
              background=[("active", "#f8fafc"), ("pressed", "#eef2f7")],
              bordercolor=[("active", ACCENT)])

    style.configure("TEntry", fieldbackground=SURFACE, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=SURFACE, padding=7,
                    insertcolor=TEXT, foreground=TEXT)
    style.map("TEntry", bordercolor=[("focus", ACCENT)])

    style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                    foreground=TEXT, bordercolor=BORDER, lightcolor=SURFACE,
                    darkcolor=SURFACE, arrowcolor=ACCENT, padding=7)
    style.map("TCombobox",
              fieldbackground=[("readonly", SURFACE)],
              bordercolor=[("focus", ACCENT)])

    style.configure("Treeview", background=ROW_ODD, fieldbackground=ROW_ODD,
                    foreground=TEXT, borderwidth=0, relief="flat",
                    rowheight=30)
    style.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", "#ffffff")])
    style.configure("Treeview.Heading", background=HEADER_BG, foreground=TEXT,
                    font=(FONT, 10, "bold"), padding=(8, 9), relief="flat",
                    borderwidth=0)
    style.map("Treeview.Heading", background=[("active", "#e8edf3")])

    style.configure("Vertical.TScrollbar", background="#cbd5e1",
                    troughcolor=BG, bordercolor=BG, arrowcolor=MUTED,
                    relief="flat", borderwidth=0)
    style.map("Vertical.TScrollbar", background=[("active", ACCENT)])


def divider(parent):
    frame = tk.Frame(parent, height=1, bg=BORDER)
    frame.pack(fill="x")
    return frame


class TrackerApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        root.geometry("1040x620")
        root.minsize(820, 460)
        root.configure(bg=BG)
        apply_style(root)

        self.url_var = tk.StringVar(value=load_config())
        self.fide_var = tk.StringVar(value="All")
        self.tc_var = tk.StringVar(value="All")
        self.sort_var = tk.StringVar(value="Start date")
        self.status_var = tk.StringVar(value="Enter the Pi's URL and press Refresh")
        self.raw_tournaments = []
        self.feed_meta = {}
        self._maps_after = None

        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_statusbar()

        for var in (self.fide_var, self.tc_var, self.sort_var):
            var.trace_add("write", self._on_filter_change)

    def _on_filter_change(self, *_args):
        self.refresh_view()

    def _build_header(self):
        header = ttk.Frame(self.root, style="Bar.TFrame", padding=(16, 14, 16, 12))
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Chess tournaments near you — FIDE & non-FIDE",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 0))
        divider(self.root)

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, style="Bar.TFrame", padding=(16, 10))
        bar.pack(fill="x")
        ttk.Label(bar, text="Server URL", style="Bar.TLabel").pack(side="left")
        entry = ttk.Entry(bar, textvariable=self.url_var, width=46)
        entry.pack(side="left", padx=(8, 8))
        ttk.Button(bar, text="Refresh", style="Accent.TButton",
                   command=self.refresh_feed).pack(side="left")
        ttk.Button(bar, text="Load sample", style="Soft.TButton",
                   command=self.load_sample).pack(side="left", padx=(8, 0))

        filters = ttk.Frame(bar, style="Bar.TFrame")
        filters.pack(side="right")
        self._filter_row(filters, "FIDE", self.fide_var, ["All", "FIDE", "Non-FIDE"])
        self._filter_row(filters, "Time control", self.tc_var,
                         ["All"] + [tc.capitalize() for tc in TIME_CONTROLS])
        self._filter_row(filters, "Sort by", self.sort_var, list(FILTER_SORTS))
        divider(self.root)

    def _filter_row(self, parent, label, variable, options):
        ttk.Label(parent, text=label, style="Bar.TLabel").pack(side="left", padx=(10, 4))
        ttk.Combobox(parent, textvariable=variable, values=options,
                     state="readonly", width=11).pack(side="left")

    def _build_table(self):
        columns = ("date", "name", "location", "dist", "fide", "u10", "tc", "category")
        headings = {
            "date": "Start",
            "name": "Tournament",
            "location": "Location",
            "dist": "Dist",
            "fide": "FIDE",
            "u10": "U-10",
            "tc": "Time Control",
            "category": "Type",
        }
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=(12, 8))

        self.table = ttk.Treeview(wrap, columns=columns, show="headings",
                                  selectmode="browse")
        for col in columns:
            self.table.heading(col, text=headings[col])
        self.table.column("date", width=80, anchor="center")
        self.table.column("name", width=340)
        self.table.column("location", width=170)
        self.table.column("dist", width=64, anchor="center")
        self.table.column("fide", width=56, anchor="center")
        self.table.column("u10", width=56, anchor="center")
        self.table.column("tc", width=90, anchor="center")
        self.table.column("category", width=110)

        self.table.tag_configure("even", background=ROW_ODD)
        self.table.tag_configure("odd", background=ROW_EVEN)

        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.table.bind("<Button-1>", self._on_location_click)
        self.table.bind("<Double-1>", self._on_location_double)

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, style="Bar.TFrame", padding=(16, 8))
        bar.pack(fill="x", side="bottom")
        divider(self.root)
        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel",
                  anchor="w").pack(fill="x")

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

    def _on_location_click(self, event):
        row = self.table.identify_row(event.y)
        if not row or self.table.identify_column(event.x) != "#3":
            return
        item = self.table.item(row)
        tag = item["tags"][0] if item["tags"] else ""
        match = [t for t in self.raw_tournaments if f"t{id(t)}" == tag]
        if not match:
            return
        location = (match[0].get("venue") or match[0].get("location") or "").strip()
        if not location:
            return
        if self._maps_after is not None:
            self.root.after_cancel(self._maps_after)
        self._maps_after = self.root.after(
            350, lambda: webbrowser.open(maps_url(location))
        )

    def _on_location_double(self, event):
        if self._maps_after is not None:
            self.root.after_cancel(self._maps_after)
            self._maps_after = None
        self.show_details(event)

    def refresh_view(self):
        for item in self.table.get_children():
            self.table.delete(item)

        fide = self.fide_var.get()
        tc = self.tc_var.get().lower()
        sort_key = FILTER_SORTS.get(self.sort_var.get(), "start_date")

        rows = []
        for t in self.raw_tournaments:
            if t.get("sport") != "chess":
                continue
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

        for index, (_, _, t) in enumerate(rows):
            fide_text = "Yes" if t.get("fide_rated") is True else ("No" if t.get("fide_rated") is False else "—")
            tc_text = (t.get("time_control") or "—").capitalize()
            dist = t.get("distance_km")
            dist_text = f"{dist:.0f} km" if isinstance(dist, (int, float)) else "—"
            self.table.insert(
                "", "end",
                values=(
                    format_date(t.get("start_date")),
                    t.get("name", "?"),
                    t.get("venue") or "-",
                    dist_text,
                    fide_text,
                    "Yes" if is_u10(t) else "—",
                    tc_text,
                    t.get("category", "—"),
                ),
                tags=(f"t{id(t)}", "even" if index % 2 == 0 else "odd"),
            )

    def show_details(self, _event=None):
        selected = self.table.selection()
        if not selected:
            return
        item = self.table.item(selected[0])
        tag = item["tags"][0] if item["tags"] else ""
        match = [t for t in self.raw_tournaments if f"t{id(t)}" == tag]
        if not match:
            return
        t = match[0]
        home_label = self.feed_meta.get("home", {}).get("label", "home")
        dist = t.get("distance_km")
        dist_text = f"{dist} km from {home_label}" if isinstance(dist, (int, float)) else "—"
        venue = t.get("venue")
        lines = [
            t.get("name", "?"),
            "",
            f"Dates        {t.get('start_date')} → {t.get('end_date') or 'TBC'}",
            f"Location     {t.get('location', '?')}",
        ]
        if venue and venue != t.get("location"):
            lines.append(f"Venue        {venue}")
        lines += [
            f"Distance     {dist_text}",
            f"FIDE rated   {t.get('fide_rated')}",
            f"U-10 friendly {'Yes' if is_u10(t) else 'No'}",
            f"Time control {t.get('time_control')}",
            f"Type         {t.get('category')}",
            f"Source       {t.get('source')}",
        ]

        win = tk.Toplevel(self.root)
        win.title(APP_NAME)
        win.configure(bg=SURFACE)
        win.resizable(True, True)
        win.transient(self.root)

        text = tk.Text(win, wrap="word", width=66, height=13,
                       bg=SURFACE, fg=TEXT, relief="flat", padx=16, pady=14,
                       font=(FONT, 10), insertbackground=TEXT)
        text.pack(fill="both", expand=True)
        text.insert("1.0", "\n".join(lines))
        if (t.get("link") or "").startswith("http"):
            text.insert("end", "\n\nLink         " + t["link"])
        text.configure(state="disabled")

        buttons = ttk.Frame(win, style="Bar.TFrame", padding=(12, 8, 12, 12))
        buttons.pack(fill="x")
        if (t.get("link") or "").startswith("http"):
            ttk.Button(buttons, text="Open link", style="Soft.TButton",
                       command=lambda: webbrowser.open(t["link"])).pack(side="right")
        ttk.Button(buttons, text="Close", style="Accent.TButton",
                   command=win.destroy).pack(side="right", padx=(0, 8))


def main():
    root = tk.Tk()
    TrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
