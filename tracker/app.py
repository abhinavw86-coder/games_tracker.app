"""Tournament Tracker — shows chess tournaments served by the Raspberry Pi
(nginx). Uses only the Python standard library so it bundles cleanly with
PyInstaller.

v2: professional layout (nav sidebar + white/pink/light-blue gradient header),
blue UI accents, offline cache, upcoming + countdown column, weekend filter,
month grouping, registration countdown + status, cost summary, best pick,
compare mode, player profile and a new-event badge.
"""

import json
import os
import platform
import re
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import date, datetime, timedelta
from tkinter import ttk, messagebox
from urllib.parse import quote
from urllib.request import urlopen

APP_NAME = "Tournament Tracker"
DEFAULT_URL = "http://pi-bookworm.local/tournaments.json"
TIME_CONTROLS = ["classical", "rapid", "blitz", "bullet"]
FILTER_SORTS = {"Start date": "start_date", "Distance": "distance_km"}
U9_RE = re.compile(r"\bu\s?[-–]?\s?9\b|\bunder\s?[-–]?\s?9\b", re.IGNORECASE)
U_CAT_RE = re.compile(r"\b(?:u\s*[-–]?\s*(\d{1,2})|under\s*[-–]?\s*(\d{1,2}))\b",
                      re.IGNORECASE)
WEEKEND_DAYS = {5, 6}

# ---- palette: white / pink / light blue background, blue accents ----
BG = "#f4f8fe"
SURFACE = "#ffffff"
SURFACE_ALT = "#f7fafd"
BORDER = "#d9e2f0"
TEXT = "#1f2937"
MUTED = "#5b6b7f"
BLUE = "#2563eb"
BLUE_DARK = "#1d4ed8"
LIGHT_BLUE = "#bfdbfe"
LIGHT_BLUE_BG = "#eaf2ff"
SOFT_PINK = "#fbd9ea"   # used only in the background gradient
SOFT_BLUE = "#d8e8fc"   # used only in the background gradient
GOOD = "#16a34a"
WARN = "#d97706"
BAD = "#dc2626"
SIDEBAR_BG = "#1c3452"
SIDEBAR_HOVER = "#29486f"
FONT = "Helvetica"


def config_dir():
    if platform.system() == "Darwin":
        base = os.path.expanduser("~/Library/Application Support/tracker.app")
    else:
        base = os.path.expanduser("~/.config/tracker")
    os.makedirs(base, exist_ok=True)
    return base


def load_config():
    default = {
        "url": DEFAULT_URL,
        "profile": {},
        "filters": {"fide": "All", "tc": "All", "sort": "Start date",
                    "search": "", "state": "All", "upcoming": True,
                    "weekend": False, "group": True, "forme": False},
        "geometry": "",
    }
    path = os.path.join(config_dir(), "config.json")
    try:
        with open(path) as fh:
            stored = json.load(fh)
        for key in default:
            if key not in stored:
                stored[key] = default[key]
        return stored
    except (OSError, ValueError):
        return default


def save_config(data):
    path = os.path.join(config_dir(), "config.json")
    try:
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass


def fetch_feed(url):
    with urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def format_date(date_text):
    if not date_text:
        return "?"
    try:
        year, month, day = date_text.split("-")[:3]
        return f"{int(day):02d}-{int(month):02d}-{year}"
    except (ValueError, IndexError):
        return date_text


def parse_iso(date_text):
    if not date_text:
        return None
    try:
        return date.fromisoformat(str(date_text)[:10])
    except ValueError:
        return None


def is_u9(tournament):
    return bool(U9_RE.search(tournament.get("name") or ""))


def u_category(name):
    match = U_CAT_RE.search(name or "")
    if not match:
        return None
    return int(match.group(1) or match.group(2))


def days_until(start_date):
    start = parse_iso(start_date)
    if start is None:
        return None
    return (start - date.today()).days


def countdown_text(start_date):
    days = days_until(start_date)
    if days is None:
        return "—"
    if days < 0:
        return "ended"
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days}d"


def is_weekend_event(t):
    start = parse_iso(t.get("start_date"))
    end = parse_iso(t.get("end_date")) or start
    if start is None:
        return False
    current = start
    while current <= end:
        if current.weekday() in WEEKEND_DAYS:
            return True
        current += timedelta(days=1)
    return False


def fee_int(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def inr(value):
    n = fee_int(value)
    if n is None:
        return "—"
    s = str(n)
    if len(s) <= 3:
        return "₹" + s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return "₹" + ",".join(parts) + "," + tail


def deadline_status(t, today=None):
    today = today or date.today()
    stored = t.get("event_status")
    if stored in ("open", "closing soon", "closed"):
        return stored
    deadline = parse_iso(t.get("reg_deadline"))
    if deadline is None:
        return None
    days = (deadline - today).days
    if days < 0:
        return "closed"
    if days <= 7:
        return "closing soon"
    return "open"


def maps_url(location):
    return "https://www.google.com/maps/search/?api=1&query=" + quote(location)


def month_label(ym):
    if not ym or len(ym) != 7:
        return "Other"
    try:
        return datetime(int(ym[:4]), int(ym[5:7]), 1).strftime("%B %Y")
    except ValueError:
        return "Other"


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


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
    style.configure("Field.TLabel", background=SURFACE, foreground=TEXT)
    style.configure("Status.TLabel", background=SURFACE, foreground=MUTED)

    style.configure("Accent.TButton", background=BLUE, foreground="#ffffff",
                    font=(FONT, 10, "bold"), padding=(18, 8), borderwidth=0,
                    focuscolor=BLUE)
    style.map("Accent.TButton",
              background=[("active", BLUE_DARK), ("pressed", BLUE_DARK),
                          ("disabled", "#9db6e8")])
    style.configure("Soft.TButton", background=LIGHT_BLUE_BG, foreground=BLUE,
                    font=(FONT, 10, "bold"), padding=(12, 8), borderwidth=0,
                    focuscolor=LIGHT_BLUE_BG)
    style.map("Soft.TButton",
              background=[("active", LIGHT_BLUE), ("pressed", LIGHT_BLUE)],
              foreground=[("active", BLUE_DARK), ("pressed", BLUE_DARK)])
    style.configure("Toggle.TButton", background=SURFACE_ALT, foreground=TEXT,
                    font=(FONT, 10), padding=(10, 7), borderwidth=1,
                    bordercolor=BORDER, focuscolor=SURFACE_ALT)
    style.map("Toggle.TButton",
              background=[("active", LIGHT_BLUE_BG)],
              bordercolor=[("active", BLUE)])

    style.configure("TCheckbutton", background=SURFACE, foreground=TEXT)
    style.map("TCheckbutton",
              background=[("active", SURFACE)],
              foreground=[("active", BLUE_DARK)])

    style.configure("TEntry", fieldbackground=SURFACE, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=SURFACE, padding=7,
                    insertcolor=TEXT, foreground=TEXT)
    style.map("TEntry", bordercolor=[("focus", BLUE)])

    style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                    foreground=TEXT, bordercolor=BORDER, lightcolor=SURFACE,
                    darkcolor=SURFACE, arrowcolor=BLUE, padding=7)
    style.map("TCombobox",
              fieldbackground=[("readonly", SURFACE)],
              bordercolor=[("focus", BLUE)])

    style.configure("Treeview", background=SURFACE_ALT, fieldbackground=SURFACE_ALT,
                    foreground=TEXT, borderwidth=0, relief="flat", rowheight=30)
    style.map("Treeview",
              background=[("selected", LIGHT_BLUE), ("active", LIGHT_BLUE_BG)],
              foreground=[("selected", BLUE_DARK), ("active", TEXT)])
    style.configure("Treeview.Heading", background=LIGHT_BLUE_BG,
                    foreground=BLUE_DARK, font=(FONT, 10, "bold"),
                    padding=(8, 9), relief="flat", borderwidth=0)
    style.map("Treeview.Heading", background=[("active", LIGHT_BLUE)])

    style.configure("Vertical.TScrollbar", background=LIGHT_BLUE,
                    troughcolor=BG, bordercolor=BG, arrowcolor=BLUE_DARK,
                    relief="flat", borderwidth=0)
    style.map("Vertical.TScrollbar", background=[("active", BLUE)])


def divider(parent, color=BORDER):
    frame = tk.Frame(parent, height=1, bg=color)
    frame.pack(fill="x")
    return frame


class TrackerApp:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.profile = self.config.get("profile", {})

        root.title(APP_NAME)
        geometry = self.config.get("geometry", "")
        if re.match(r"^\d+x\d+[+-]\d+[+-]\d+$", geometry):
            root.geometry(geometry)
        else:
            root.geometry("1280x720")
        root.minsize(1000, 560)
        root.configure(bg=BG)
        self._set_window_icon(root)
        self._start_maximized(root)

        filters = self.config.get("filters", {})
        self.url_var = tk.StringVar(value=self.config.get("url", DEFAULT_URL))
        self.fide_var = tk.StringVar(value=filters.get("fide", "All"))
        self.tc_var = tk.StringVar(value=filters.get("tc", "All"))
        self.sort_var = tk.StringVar(value=filters.get("sort", "Start date"))
        self.search_var = tk.StringVar(value=filters.get("search", ""))
        self.state_var = tk.StringVar(value=filters.get("state", "All"))
        self.upcoming_var = tk.BooleanVar(value=filters.get("upcoming", True))
        self.weekend_var = tk.BooleanVar(value=filters.get("weekend", False))
        self.group_var = tk.BooleanVar(value=filters.get("group", True))
        self.forme_var = tk.BooleanVar(value=filters.get("forme", False))
        self.status_var = tk.StringVar(value="Enter the Pi's URL and press Refresh")
        self._badge_text = tk.StringVar(value="")

        self.raw_tournaments = []
        self.feed_meta = {}
        self._maps_after = None
        self._last_ids = None
        self._offline = False

        apply_style(root)
        self._build_sidebar()
        self._build_main()

        for var in (self.fide_var, self.tc_var, self.sort_var, self.search_var,
                    self.state_var, self.upcoming_var, self.weekend_var,
                    self.group_var, self.forme_var):
            var.trace_add("write", self._on_filter_change)

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<Control-q>", self._on_close)
        root.bind("<Escape>", self._toggle_fullscreen)
        root.bind("<F11>", self._toggle_fullscreen)

        cached = self._load_cache_feed()
        if cached:
            self._feed_loaded(cached, cached=True)

    # ---------- UI ----------

    def _icon_path(self):
        if getattr(sys, "_MEIPASS", None):
            return os.path.join(sys._MEIPASS, "tracker-512.png")
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "scripts", "icons", "tracker-512.png")
        return path if os.path.exists(path) else None

    def _logo_photo(self, root, target):
        path = self._icon_path()
        if not path:
            return None
        try:
            image = tk.PhotoImage(file=path)
        except tk.TclError:
            return None
        if image.width() > target * 2:
            image = image.subsample(image.width() // target)
        return image

    def _set_window_icon(self, root):
        image = self._logo_photo(root, 128)
        if image is not None:
            try:
                root.iconphoto(True, image)
            except tk.TclError:
                pass

    def _start_maximized(self, root):
        try:
            if platform.system() == "Darwin":
                root.attributes("-zoomed", True)
            else:
                root.state("zoomed")
            return
        except tk.TclError:
            pass
        try:
            root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}")
        except tk.TclError:
            pass

    def _build_main(self):
        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        self._build_header(main)
        self._build_toolbar(main)
        self._build_table(main)
        self._build_statusbar(main)

    def _nav(self, parent, text, command, active=False):
        bg = LIGHT_BLUE_BG if active else SIDEBAR_BG
        fg = BLUE_DARK if active else "#e8effa"
        font = (FONT, 11, "bold") if active else (FONT, 11)
        button = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                           activebackground=bg, activeforeground=fg,
                           relief="flat", bd=0, anchor="w", padx=20, pady=10,
                           font=font, cursor="hand2")
        button.pack(fill="x")
        if not active:
            button.configure(activebackground=SIDEBAR_HOVER, activeforeground="#ffffff")
        return button

    def _build_sidebar(self):
        sidebar = tk.Frame(self.root, bg=SIDEBAR_BG, width=212)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        logo = tk.Frame(sidebar, bg=SIDEBAR_BG)
        logo.pack(fill="x", padx=18, pady=(18, 4))
        self._logo_img = self._logo_photo(self.root, 36)
        if self._logo_img is not None:
            tk.Label(logo, image=self._logo_img, bg=SIDEBAR_BG).pack(side="left")
        else:
            mark = tk.Canvas(logo, width=36, height=36, bg=SIDEBAR_BG, highlightthickness=0)
            mark.pack(side="left")
            mark.create_oval(9, 9, 27, 27, fill=LIGHT_BLUE, outline="")
            mark.create_oval(16, 3, 20, 7, fill=LIGHT_BLUE, outline="")
            mark.create_polygon(12, 14, 24, 14, 22, 27, 14, 27,
                                fill=LIGHT_BLUE, outline="")
            mark.create_oval(14, 28, 22, 33, fill=LIGHT_BLUE, outline="")
            mark.create_oval(23, 21, 30, 28, fill=BLUE, outline="")
        name = tk.Label(logo, text=APP_NAME, bg=SIDEBAR_BG, fg="#ffffff",
                        font=(FONT, 13, "bold"), anchor="w", justify="left",
                        wraplength=140)
        name.pack(side="left", padx=(10, 0))
        tk.Label(sidebar, text="CHESS · FIDE · LOCAL", bg=SIDEBAR_BG,
                 fg="#9fb8d6", font=(FONT, 8), anchor="w").pack(fill="x",
                                                                padx=18,
                                                                pady=(0, 12))

        tk.Frame(sidebar, bg=SIDEBAR_HOVER, height=1).pack(fill="x", padx=14)

        tk.Label(sidebar, text="VIEWS", bg=SIDEBAR_BG, fg="#9fb8d6",
                 font=(FONT, 8, "bold"), anchor="w").pack(fill="x",
                                                          padx=20, pady=(14, 4))
        self._nav(sidebar, "Tournaments", self._focus_table, active=True)
        self._nav(sidebar, "Best pick", self.show_best_pick)
        self._nav(sidebar, "Compare", self.show_compare)
        self._nav(sidebar, "Cost summary", self.show_cost_summary)
        self._nav(sidebar, "Player profile", self.show_profile)

        tk.Frame(sidebar, bg=SIDEBAR_HOVER, height=1).pack(fill="x",
                                                           padx=14, pady=(10, 0))

        tk.Label(sidebar, text="FEED", bg=SIDEBAR_BG, fg="#9fb8d6",
                 font=(FONT, 8, "bold"), anchor="w").pack(fill="x",
                                                          padx=20, pady=(12, 0))
        feed = tk.Frame(sidebar, bg=SIDEBAR_BG)
        feed.pack(fill="x", padx=16, pady=(6, 0))
        self.url_entry = tk.Entry(feed, textvariable=self.url_var, bg="#ffffff",
                                  fg=TEXT, insertbackground=TEXT, relief="flat",
                                  highlightthickness=1, highlightbackground=BORDER,
                                  highlightcolor=BLUE, font=(FONT, 9))
        self.url_entry.pack(fill="x")
        tk.Label(feed, text="Server URL", bg=SIDEBAR_BG, fg="#9fb8d6",
                 font=(FONT, 8)).pack(anchor="w", pady=(3, 6))

        buttons = tk.Frame(feed, bg=SIDEBAR_BG)
        buttons.pack(fill="x", pady=(2, 0))
        tk.Button(buttons, text="Refresh", command=self.refresh_feed,
                  bg=BLUE, fg="#ffffff", activebackground=BLUE_DARK,
                  activeforeground="#ffffff", relief="flat", bd=0,
                  padx=12, pady=8, font=(FONT, 10, "bold"),
                  cursor="hand2").pack(side="left", expand=True, fill="x")
        tk.Button(buttons, text="Load sample", command=self.load_sample,
                  bg=SIDEBAR_HOVER, fg="#e8effa", activebackground="#37618f",
                  activeforeground="#ffffff", relief="flat", bd=0,
                  padx=12, pady=8, font=(FONT, 10),
                  cursor="hand2").pack(side="left", padx=(8, 0), expand=True,
                                       fill="x")

    def _toggle_fullscreen(self, _event=None):
        try:
            current = bool(self.root.attributes("-fullscreen"))
        except tk.TclError:
            return
        self.root.attributes("-fullscreen", not current)

    def _focus_table(self):
        if hasattr(self, "table"):
            self.table.yview_moveto(0)
            self.table.focus_set()

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=SURFACE)
        header.pack(fill="x")
        canvas = tk.Canvas(header, height=88, bg=SURFACE, highlightthickness=0)
        canvas.pack(fill="x")
        white = (255, 255, 255)
        pink = tuple(int(SOFT_PINK[i:i + 2], 16) for i in (1, 3, 5))
        blue = tuple(int(SOFT_BLUE[i:i + 2], 16) for i in (1, 3, 5))
        half = 44
        for y in range(88):
            if y < half:
                color = "#%02x%02x%02x" % _mix(white, pink, y / half)
            else:
                color = "#%02x%02x%02x" % _mix(pink, blue, (y - half) / half)
            canvas.create_line(0, y, 3000, y, fill=color)
        canvas.create_rectangle(0, 86, 3000, 88, fill=LIGHT_BLUE, outline="")
        canvas.create_text(24, 19, anchor="w", text=APP_NAME,
                           font=(FONT, 19, "bold"), fill=BLUE_DARK)
        canvas.create_text(24, 47, anchor="w",
                           text="Chess tournaments near you — FIDE & non-FIDE",
                           font=(FONT, 10), fill=MUTED)

    def _build_toolbar(self, parent):
        bar = ttk.Frame(parent, style="Bar.TFrame", padding=(16, 10))
        bar.pack(fill="x")
        self._make_toggle(bar, "Upcoming only", self.upcoming_var)
        self._make_toggle(bar, "Weekends", self.weekend_var)
        self._make_toggle(bar, "Group by month", self.group_var)
        self._make_toggle(bar, "For me", self.forme_var)

        ttk.Label(bar, text="Search", style="Field.TLabel").pack(side="right", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.search_var, width=16).pack(side="right")
        self._state_combobox = self._filter_row(bar, "State", self.state_var, ["All"])
        self._filter_row(bar, "FIDE", self.fide_var, ["All", "FIDE", "Non-FIDE"])
        self._filter_row(bar, "Time control", self.tc_var,
                         ["All"] + [tc.capitalize() for tc in TIME_CONTROLS])
        self._filter_row(bar, "Sort by", self.sort_var, list(FILTER_SORTS))
        divider(parent)

    def _make_toggle(self, parent, label, variable):
        ttk.Checkbutton(parent, text=label, variable=variable,
                        style="TCheckbutton").pack(side="left", padx=(0, 14))

    def _filter_row(self, parent, label, variable, options):
        ttk.Label(parent, text=label, style="Field.TLabel").pack(side="left", padx=(10, 4))
        box = ttk.Combobox(parent, textvariable=variable, values=options,
                           state="readonly", width=10)
        box.pack(side="left")
        return box

    def _build_table(self, parent):
        columns = ("date", "name", "location", "due", "dist", "fide", "u9", "tc", "category")
        headings = {
            "date": "Start",
            "name": "Tournament",
            "location": "Location",
            "due": "Due",
            "dist": "Dist",
            "fide": "FIDE",
            "u9": "U-9",
            "tc": "Time Control",
            "category": "Type",
        }
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=(12, 8))

        self.table = ttk.Treeview(wrap, columns=columns, show="headings",
                                  selectmode="extended")
        for col in columns:
            self.table.heading(col, text=headings[col])
        self.table.column("date", width=80, anchor="center")
        self.table.column("name", width=330)
        self.table.column("location", width=180)
        self.table.column("due", width=76, anchor="center")
        self.table.column("dist", width=58, anchor="center")
        self.table.column("fide", width=52, anchor="center")
        self.table.column("u9", width=52, anchor="center")
        self.table.column("tc", width=88, anchor="center")
        self.table.column("category", width=100)

        self.table.tag_configure("even", background=SURFACE_ALT)
        self.table.tag_configure("odd", background=SURFACE)
        self.table.tag_configure("group", background=LIGHT_BLUE_BG,
                                 foreground=BLUE_DARK, font=(FONT, 10, "bold"))
        self.table.tag_configure("due", foreground=WARN)
        self.table.tag_configure("past", foreground=MUTED)

        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.table.bind("<Button-1>", self._on_click)
        self.table.bind("<Double-1>", self._on_double)
        self.table.bind("<Return>", self.show_details)

    def _build_statusbar(self, parent):
        bar = ttk.Frame(parent, style="Bar.TFrame", padding=(16, 8))
        bar.pack(fill="x", side="bottom")
        divider(parent)
        self.badge_label = ttk.Label(bar, textvariable=self._badge_text,
                                     background=BLUE, foreground="#ffffff",
                                     font=(FONT, 9, "bold"), padding=(8, 2))
        self.badge_label.pack(side="left", padx=(0, 10))
        self.badge_label.bind("<Button-1>", self._clear_badge)
        self.status_label = ttk.Label(bar, textvariable=self.status_var,
                                      style="Status.TLabel", anchor="w")
        self.status_label.pack(fill="x")

    # ---------- data ----------

    def refresh_feed(self):
        url = self.url_var.get().strip() or DEFAULT_URL
        self.config["url"] = url
        save_config(self.config)
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
        cached = self._load_cache_feed()
        if cached is not None:
            self._feed_loaded(cached, cached=True)
            self.status_var.set(f"● OFFLINE — showing cached feed · {error}")
            self.status_label.configure(foreground=BAD)
            return
        self.status_var.set(f"Could not reach the Pi: {error}")
        self.status_label.configure(foreground=BAD)
        messagebox.showerror(APP_NAME, f"Could not fetch tournaments:\n{error}\n\n"
                             f"Check the server URL and that the Pi is on and nginx is running.")

    def _cache_path(self):
        return os.path.join(config_dir(), "feed_cache.json")

    def _save_cache_feed(self, data):
        try:
            with open(self._cache_path(), "w") as fh:
                json.dump(data, fh)
        except OSError:
            pass

    def _load_cache_feed(self):
        try:
            with open(self._cache_path()) as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def _feed_loaded(self, data, cached=False):
        self.raw_tournaments = data.get("tournaments", [])
        self.feed_meta = data
        self._offline = cached
        home = data.get("home", {})
        when = data.get("generated_at", "").replace("T", " ")[:16]
        where = f"near {home.get('label', 'home')}" if home else ""

        current_ids = [t.get("id") for t in self.raw_tournaments]
        if self._last_ids is not None:
            new_ids = [i for i in current_ids if i not in set(self._last_ids)]
            if new_ids and not cached:
                self._set_badge(len(new_ids))
        self._last_ids = current_ids

        states = sorted({t["state"] for t in self.raw_tournaments if t.get("state")})
        if hasattr(self, "_state_combobox") and self._state_combobox is not None:
            self._state_combobox.configure(values=["All"] + states)
        if self.state_var.get() not in ["All"] + states:
            self.state_var.set("All")

        if not cached:
            self._save_cache_feed(data)
            self.status_label.configure(foreground=MUTED)
            self.status_var.set(
                f"{len(self.raw_tournaments)} tournaments {where} · feed updated {when}"
            )
        self.refresh_view()

    def load_sample(self):
        sample_path = self._sample_path()
        try:
            with open(sample_path) as fh:
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
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "sample.json")

    # ---------- filtering / rendering ----------

    def _on_filter_change(self, *_args):
        if hasattr(self, "table"):
            self.refresh_view()

    def _matches(self, t):
        if t.get("sport") != "chess":
            return False
        fide = self.fide_var.get()
        if fide == "FIDE" and not t.get("fide_rated"):
            return False
        if fide == "Non-FIDE" and t.get("fide_rated"):
            return False
        tc = self.tc_var.get().lower()
        if tc != "all" and (t.get("time_control") or "classical").lower() != tc:
            return False
        state = self.state_var.get()
        if state != "All" and t.get("state") != state:
            return False
        if self.upcoming_var.get():
            days = days_until(t.get("start_date"))
            if days is None or days < 0:
                return False
        if self.weekend_var.get() and not is_weekend_event(t):
            return False
        if self.forme_var.get() and not self._eligible(t):
            return False
        query = self.search_var.get().strip().lower()
        if query:
            hay = " ".join(str(t.get(k) or "") for k in
                           ("name", "venue", "location", "state"))
            if query not in hay.lower():
                return False
        return True

    def _eligible(self, t):
        age = self.profile.get("age")
        cat = u_category(t.get("name", ""))
        if age and cat and age >= cat:
            return False
        budget = self.profile.get("budget")
        fee = fee_int(t.get("entry_fee"))
        if budget and fee and fee > budget:
            return False
        return True

    def _sorted(self, filtered):
        sort_key = FILTER_SORTS.get(self.sort_var.get(), "start_date")
        keyed = []
        for t in filtered:
            start = t.get("start_date", "") or "9999-99-99"
            dist = t.get("distance_km")
            dist = dist if isinstance(dist, (int, float)) else float("inf")
            keyed.append((start, dist, t))
        if sort_key == "distance_km":
            keyed.sort(key=lambda r: (r[1], r[0]))
        else:
            keyed.sort(key=lambda r: (r[0], r[1]))
        return [t for _, _, t in keyed]

    def refresh_view(self):
        for item in self.table.get_children():
            self.table.delete(item)
        tournaments = self._sorted([t for t in self.raw_tournaments if self._matches(t)])

        if self.group_var.get():
            groups = {}
            for index, t in enumerate(tournaments):
                ym = (t.get("start_date") or "9999-99")[:7]
                if ym not in groups:
                    iid = f"m{ym}"
                    self.table.insert("", "end", iid=iid,
                                      values=(month_label(ym), "", "", "", "",
                                              "", "", "", ""),
                                      tags=("group",))
                    groups[ym] = iid
                self._insert_row(groups[ym], t, index)
        else:
            for index, t in enumerate(tournaments):
                self._insert_row("", t, index)

    def _insert_row(self, parent, t, index):
        tags = [f"t{id(t)}", "even" if index % 2 == 0 else "odd"]
        days = days_until(t.get("start_date"))
        if days is not None:
            if days < 0:
                tags.append("past")
            elif days <= 3:
                tags.append("due")
        fide_text = "Yes" if t.get("fide_rated") is True else (
            "No" if t.get("fide_rated") is False else "—")
        tc_text = (t.get("time_control") or "—").capitalize()
        dist = t.get("distance_km")
        dist_text = f"{dist:.0f} km" if isinstance(dist, (int, float)) else "—"
        self.table.insert(
            parent, "end",
            values=(
                format_date(t.get("start_date")),
                t.get("name", "?"),
                t.get("venue") or "-",
                countdown_text(t.get("start_date")),
                dist_text,
                fide_text,
                "Yes" if is_u9(t) else "—",
                tc_text,
                t.get("category", "—"),
            ),
            tags=tuple(tags),
        )

    # ---------- interactions ----------

    def _on_click(self, event):
        row = self.table.identify_row(event.y)
        if not row:
            return
        item = self.table.item(row)
        tags = item["tags"]
        if tags and tags[0] == "group":
            self.table.item(row, open=not self.table.item(row)["open"])
            return
        if self.table.identify_column(event.x) != "#3":
            return
        tag = tags[0] if tags else ""
        match = [t for t in self.raw_tournaments if f"t{id(t)}" == tag]
        if not match:
            return
        location = (match[0].get("venue") or match[0].get("location") or "").strip()
        if not location:
            return
        if self._maps_after is not None:
            self.root.after_cancel(self._maps_after)
        self._maps_after = self.root.after(
            350, lambda: webbrowser.open(maps_url(location)))

    def _on_double(self, event):
        if self._maps_after is not None:
            self.root.after_cancel(self._maps_after)
            self._maps_after = None
        row = self.table.identify_row(event.y)
        if row:
            item = self.table.item(row)
            if item["tags"] and item["tags"][0] == "group":
                self.table.item(row, open=not self.table.item(row)["open"])
                return
        self.show_details(event)

    def _selected(self):
        picked = []
        for row in self.table.selection():
            tags = self.table.item(row)["tags"]
            if tags and tags[0] == "group":
                continue
            tag = tags[0] if tags else ""
            match = [t for t in self.raw_tournaments if f"t{id(t)}" == tag]
            if match:
                picked.append(match[0])
        return picked

    # ---------- details ----------

    def show_details(self, _event=None):
        selected = self.table.selection()
        if not selected:
            return
        item = self.table.item(selected[0])
        tags = item["tags"]
        if tags and tags[0] == "group":
            return
        tag = tags[0] if tags else ""
        match = [t for t in self.raw_tournaments if f"t{id(t)}" == tag]
        if not match:
            return
        t = match[0]
        home_label = self.feed_meta.get("home", {}).get("label", "home")
        dist = t.get("distance_km")
        dist_text = f"{dist} km from {home_label}" if isinstance(dist, (int, float)) else "—"
        venue = t.get("venue")
        status = deadline_status(t)
        status_text = status or "—"
        status_color = {"open": GOOD, "closing soon": WARN,
                        "closed": BAD}.get(status, MUTED)
        deadline = t.get("reg_deadline")
        deadline_text = format_date(deadline) if deadline else "—"

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
            f"U-9 friendly {'Yes' if is_u9(t) else 'No'}",
            f"Time control {t.get('time_control')}",
            f"Type         {t.get('category')}",
            f"Entry fee    {inr(t.get('entry_fee'))}",
            f"Prize fund   {inr(t.get('prize_fund'))}",
            f"Reg deadline {deadline_text}",
            f"Status       {status_text}",
            f"Source       {t.get('source')}",
        ]

        win = tk.Toplevel(self.root)
        win.title(APP_NAME)
        win.configure(bg=SURFACE)
        win.resizable(True, True)
        win.transient(self.root)

        text = tk.Text(win, wrap="word", width=70, height=16,
                       bg=SURFACE, fg=TEXT, relief="flat", padx=16, pady=14,
                       font=(FONT, 10), insertbackground=TEXT)
        text.pack(fill="both", expand=True)
        text.insert("1.0", "\n".join(lines))
        status_idx = "end-1c linestart"
        for idx in range(len(lines)):
            if "Status" in lines[idx]:
                status_idx = f"{idx + 1}.14"
        text.tag_add("status", status_idx, "end-1c")
        text.tag_configure("status", foreground=status_color,
                           font=(FONT, 10, "bold"))
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

    # ---------- dialogs ----------

    def _dialog(self, title, width=520, height=300):
        win = tk.Toplevel(self.root)
        win.title(f"{APP_NAME} — {title}")
        win.configure(bg=SURFACE)
        win.geometry(f"{width}x{height}")
        win.transient(self.root)
        win.resizable(True, True)
        return win

    def show_profile(self):
        win = self._dialog("Profile", 400, 320)
        win.resizable(False, False)
        body = ttk.Frame(win, style="Bar.TFrame", padding=18)
        body.pack(fill="both", expand=True)
        fields = {}

        def row(label, key, default):
            ttk.Label(body, text=label, style="Field.TLabel").pack(anchor="w", pady=(8, 2))
            var = tk.StringVar(value=str(self.profile.get(key, "")) if default else "")
            if not default and key in self.profile:
                var.set(str(self.profile[key]))
            ttk.Entry(body, textvariable=var, width=24).pack(anchor="w")
            fields[key] = var

        row("Age (optional)", "age", False)
        row("FIDE rating (optional)", "rating", False)
        row("Monthly budget ₹ (optional)", "budget", False)
        row("Max distance km (optional)", "max_km", False)

        def save():
            for key, var in fields.items():
                value = var.get().strip()
                if value == "":
                    self.profile.pop(key, None)
                else:
                    try:
                        self.profile[key] = int(value)
                    except ValueError:
                        messagebox.showerror(APP_NAME, f"'{value}' is not a whole number.",
                                             parent=win)
                        return
            self.config["profile"] = self.profile
            save_config(self.config)
            self.refresh_view()
            win.destroy()

        bar = ttk.Frame(win, style="Bar.TFrame", padding=(12, 8, 12, 12))
        bar.pack(fill="x")
        ttk.Button(bar, text="Save", style="Accent.TButton", command=save).pack(side="right")
        ttk.Button(bar, text="Cancel", style="Soft.TButton",
                   command=win.destroy).pack(side="right", padx=(0, 8))

    def show_cost_summary(self):
        upcoming = [t for t in self.raw_tournaments
                    if days_until(t.get("start_date")) is not None
                    and days_until(t.get("start_date")) >= 0]
        with_fee = [t for t in upcoming if fee_int(t.get("entry_fee")) is not None]
        by_month = {}
        for t in with_fee:
            ym = (t.get("start_date") or "?")[:7]
            by_month.setdefault(ym, []).append(t)

        cheapest = None
        for t in with_fee:
            if is_weekend_event(t):
                if cheapest is None or fee_int(t["entry_fee"]) < fee_int(cheapest["entry_fee"]):
                    cheapest = t

        total = sum(fee_int(t.get("entry_fee")) or 0 for t in with_fee)
        win = self._dialog("Cost summary", 520, 340)
        text = tk.Text(win, wrap="word", bg=SURFACE, fg=TEXT, relief="flat",
                       padx=18, pady=14, font=(FONT, 11), insertbackground=TEXT)
        text.pack(fill="both", expand=True)
        lines = ["Upcoming events with a known entry fee:",
                 f"  {len(with_fee)} events · total {inr(total)}", ""]
        for ym in sorted(by_month):
            month_total = sum(fee_int(t.get("entry_fee")) or 0 for t in by_month[ym])
            lines.append(f"  {month_label(ym):<12} {len(by_month[ym]):>3} events "
                         f"· {inr(month_total)}")
        lines.append("")
        if cheapest:
            start = format_date(cheapest.get("start_date"))
            lines.append(f"Cheapest weekend option:")
            lines.append(f"  {cheapest.get('name')}")
            lines.append(f"  {start} · {cheapest.get('location')} · "
                         f"{inr(cheapest.get('entry_fee'))}")
        else:
            lines.append("No weekend events with a known entry fee.")
        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")
        bar = ttk.Frame(win, style="Bar.TFrame", padding=(12, 8, 12, 12))
        bar.pack(fill="x")
        ttk.Button(bar, text="Close", style="Accent.TButton",
                   command=win.destroy).pack(side="right")

    def show_best_pick(self):
        if not any(self.profile.get(k) for k in ("age", "rating", "budget", "max_km")):
            messagebox.showinfo(APP_NAME,
                                "Set up your player profile first (Profile button) so I know "
                                "what to look for.")
            return

        scored = []
        for t in self.raw_tournaments:
            days = days_until(t.get("start_date"))
            if days is None or days < 0:
                continue
            score, reasons = self._score(t)
            scored.append((score, reasons, t))
        scored.sort(key=lambda s: (-s[0], days_until(s[2].get("start_date")) or 0))

        win = self._dialog("Best pick", 560, 400)
        text = tk.Text(win, wrap="word", bg=SURFACE, fg=TEXT, relief="flat",
                       padx=18, pady=14, font=(FONT, 11), insertbackground=TEXT)
        text.pack(fill="both", expand=True)
        if not scored:
            text.insert("1.0", "No upcoming tournaments to rank.")
        for index, (score, reasons, t) in enumerate(scored[:5]):
            title = f"{index + 1}. {t.get('name')}  ({score:+d})"
            text.insert("end", title + "\n")
            text.tag_add(f"head{index}", f"{index * 2 + 1}.0", f"{index * 2 + 1}.end")
            text.tag_configure(f"head{index}", foreground=BLUE_DARK,
                               font=(FONT, 11, "bold"))
            text.insert("end", "   " + " · ".join(reasons) + "\n\n")
        text.configure(state="disabled")
        bar = ttk.Frame(win, style="Bar.TFrame", padding=(12, 8, 12, 12))
        bar.pack(fill="x")
        ttk.Button(bar, text="Close", style="Accent.TButton",
                   command=win.destroy).pack(side="right")

    def _score(self, t):
        score = 0
        reasons = []
        profile = self.profile
        age = profile.get("age")
        cat = u_category(t.get("name", ""))
        if age:
            if cat is None:
                score += 5
            elif age < cat:
                score += 40
                reasons.append("you're in this age group")
            else:
                score -= 40
                reasons.append("you're too old for this section")
        if profile.get("rating") and t.get("fide_rated"):
            score += 10
            reasons.append("FIDE rated")
        budget = profile.get("budget")
        fee = fee_int(t.get("entry_fee"))
        if budget and fee:
            if fee <= budget:
                score += 20
                reasons.append(f"fits your ₹{budget} budget")
            else:
                score -= 30
                reasons.append(f"over your ₹{budget} budget")
        max_km = profile.get("max_km")
        dist = t.get("distance_km")
        if max_km and isinstance(dist, (int, float)):
            if dist <= max_km:
                score += 15
                reasons.append(f"{dist:.0f} km away")
            else:
                score -= 15
                reasons.append(f"{dist:.0f} km is far")
        status = deadline_status(t)
        if status == "closed":
            score -= 100
            reasons.append("registration closed")
        elif status == "closing soon":
            score += 5
            reasons.append("registration closing soon")
        if is_weekend_event(t):
            score += 5
            reasons.append("weekend")
        if is_u9(t) and not (age and age <= 9):
            score -= 10
        return score, (reasons or ["no profile match yet"])

    def show_compare(self):
        picked = self._selected()
        if len(picked) < 2 or len(picked) > 3:
            messagebox.showinfo(APP_NAME,
                                "Select 2–3 tournaments (Ctrl/Shift-click) and press Compare.")
            return

        rows = [
            ("Start", lambda t: format_date(t.get("start_date"))),
            ("End", lambda t: format_date(t.get("end_date")) or "TBC"),
            ("Location", lambda t: t.get("location", "—")),
            ("Venue", lambda t: t.get("venue") or "-"),
            ("Distance", lambda t: f"{t.get('distance_km'):.0f} km"
             if isinstance(t.get("distance_km"), (int, float)) else "—"),
            ("FIDE rated", lambda t: t.get("fide_rated")),
            ("U-9", lambda t: "Yes" if is_u9(t) else "No"),
            ("Time control", lambda t: t.get("time_control", "—")),
            ("Type", lambda t: t.get("category", "—")),
            ("Entry fee", lambda t: inr(t.get("entry_fee"))),
            ("Prize fund", lambda t: inr(t.get("prize_fund"))),
            ("Reg deadline", lambda t: format_date(t.get("reg_deadline")) or "—"),
            ("Status", lambda t: deadline_status(t) or "—"),
        ]

        win = self._dialog("Compare", 720, 460)
        canvas = tk.Canvas(win, bg=SURFACE, highlightthickness=0)
        frame = ttk.Frame(canvas, style="Bar.TFrame", padding=16)
        sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")

        n = len(picked)
        for c, t in enumerate(picked):
            ttk.Label(frame, text=t.get("name", "?"),
                      style="Field.TLabel", font=(FONT, 11, "bold"),
                      wraplength=200).grid(row=0, column=c + 1, padx=10, pady=4, sticky="n")
            if (t.get("link") or "").startswith("http"):
                ttk.Button(frame, text="Open link", style="Soft.TButton",
                           command=lambda link=t["link"]: webbrowser.open(link)
                           ).grid(row=1, column=c + 1, pady=(0, 10))

        fee_values = [fee_int(t.get("entry_fee")) for t in picked]
        best_fee = min(f for f in fee_values if f is not None) if any(f is not None for f in fee_values) else None
        dist_values = [t.get("distance_km") for t in picked]
        best_dist = min(d for d in dist_values if isinstance(d, (int, float))) \
            if any(isinstance(d, (int, float)) for d in dist_values) else None

        for r, (label, getter) in enumerate(rows, start=2):
            ttk.Label(frame, text=label, style="Field.TLabel",
                      font=(FONT, 10, "bold")).grid(row=r, column=0, sticky="nw",
                                                    padx=(0, 10), pady=3)
            for c, t in enumerate(picked):
                value = getter(t)
                color = TEXT
                font = (FONT, 10)
                if label == "Entry fee" and best_fee is not None and fee_int(value) == best_fee:
                    color, font = GOOD, (FONT, 10, "bold")
                if label == "Distance" and best_dist is not None:
                    dist = t.get("distance_km")
                    if isinstance(dist, (int, float)) and dist == best_dist:
                        color, font = BLUE_DARK, (FONT, 10, "bold")
                if label == "Status":
                    color = {"open": GOOD, "closing soon": WARN,
                             "closed": BAD}.get(value, MUTED)
                ttk.Label(frame, text=str(value), foreground=color,
                          font=font, background=SURFACE,
                          wraplength=200).grid(row=r, column=c + 1,
                                               sticky="nw", padx=10, pady=3)

        def on_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", on_configure)

        bar = ttk.Frame(win, style="Bar.TFrame", padding=(12, 8, 12, 12))
        bar.pack(fill="x", side="bottom")
        ttk.Button(bar, text="Close", style="Accent.TButton",
                   command=win.destroy).pack(side="right")

    # ---------- badge ----------

    def _set_badge(self, count):
        self._badge_text.set(f"▲ {count} new")
        self.badge_label.configure(textvariable=self._badge_text)

    def _clear_badge(self, _event=None):
        self._badge_text.set("")
        if self._last_ids is not None:
            self._last_ids = list(self._last_ids)

    # ---------- lifecycle ----------

    def _on_close(self, _event=None):
        geometry = self.root.geometry()
        self.config["geometry"] = geometry
        self.config["filters"] = {
            "fide": self.fide_var.get(), "tc": self.tc_var.get(),
            "sort": self.sort_var.get(), "search": self.search_var.get(),
            "state": self.state_var.get(), "upcoming": self.upcoming_var.get(),
            "weekend": self.weekend_var.get(), "group": self.group_var.get(),
            "forme": self.forme_var.get(),
        }
        save_config(self.config)
        self.root.destroy()


def main():
    root = tk.Tk()
    TrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
