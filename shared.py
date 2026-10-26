"""
Code shared by every CrashLens page: data loading and cleaning, the
CrashScore comparison baseline, search matching, and small helpers.

The scoring formula itself lives in priority_score.py and is unchanged.
"""
import difflib
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from priority_score import calculate_raw_severity, score_intersection

# ---------------------------------------------------------------------------
# Data file and coverage facts
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent

# The data path is relative to this file (not the current folder), so the app
# starts the same way locally and on Streamlit Community Cloud.
# Tests point CRASHLENS_DATA at a small test file instead.
DATA_PATH = Path(os.environ.get("CRASHLENS_DATA", APP_DIR / "data" / "ct_crashes_sample.csv"))

DATA_SOURCE = "Connecticut Crash Data Repository (UConn Connecticut Transportation Safety Research Center)"
# CrashLens's goal, worded the same way on every page.
MISSION = ("CrashLens helps teen drivers and their parents find safer routes, ones with fewer recorded crashes, "
           "and drive them in Google Maps.")

# How CrashLens describes its data everywhere in the app (kept in one place so it stays consistent).
SCOPE_NOTE = ("This version of CrashLens uses a limited sample of police-reported crash records for the "
              "Town of South Windsor, CT.")
GROWTH_NOTE = ("It is built so more towns and more crash records can be added as CrashLens grows into a "
               "full app; the same rules and CrashScore would apply.")

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Most Severe Injury uses the standard KABCO codes.
#   K = fatal, A = suspected serious injury, B = suspected minor injury,
#   C = possible injury, O = no apparent injury.
INJURY_CODES = {"K", "A", "B", "C"}
VALID_SEVERITY_CODES = INJURY_CODES | {"O"}

TYPE_COLUMN = "Manner of Crash / Collision Impact Text Format"


class DataUnavailable(Exception):
    """The crash data file is missing or can't be read."""


# ---------------------------------------------------------------------------
# Road-name normalization (same rules for what the user types and for the data)
# ---------------------------------------------------------------------------
# Each whole word on the left becomes the standard spelling on the right.
# Whole words only, so "av" never changes the middle of "avery".
ROAD_WORD_MAP = {
    "road": "rd",
    "street": "st",
    "avenue": "ave",
    "av": "ave",
    "drive": "dr",
}


def normalize_road_input(text):
    if not isinstance(text, str):
        return ""
    words = text.strip().lower().split()
    return " ".join(ROAD_WORD_MAP.get(word, word) for word in words)


def normalize_road_column(series):
    # Same normalization for the data, so both sides use one spelling.
    return series.fillna("").astype(str).apply(normalize_road_input)


def normalize_town(text):
    if not isinstance(text, str):
        return ""
    return " ".join(text.strip().lower().split())


def clean_severity_code(value):
    """Returns K/A/B/C/O, or None when the value is blank or not a known code."""
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    return code if code in VALID_SEVERITY_CODES else None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading Connecticut crash records…")
def load_data(path=str(DATA_PATH)):
    """
    Reads the crash CSV once and prepares it for searching:
      * one row per crash (duplicate CrashIds are counted once)
      * Most Severe Injury cleaned to K/A/B/C/O, with blanks marked unknown
      * normalized town/road columns so every search compares like with like
    """
    try:
        raw = pd.read_csv(path)
    except FileNotFoundError:
        raise DataUnavailable(f"The crash data file was not found at {path}.")
    except Exception as problem:  # unreadable / corrupt file
        raise DataUnavailable(f"The crash data file could not be read ({problem}).")

    rows_in_file = len(raw)
    df = raw.drop_duplicates(subset="CrashId", keep="first").copy()

    df["severity_code"] = df["Most Severe Injury"].apply(clean_severity_code)
    df["is_injury"] = df["severity_code"].isin(INJURY_CODES)
    df["is_fatal"] = df["severity_code"] == "K"
    df["severity_known"] = df["severity_code"].notna()

    df["town_key"] = df["Town Name"].apply(normalize_town)
    df["road_key"] = normalize_road_column(df["Roadway Name"])
    df["cross_key"] = normalize_road_column(df["Intersecting Roadway Name"])

    df.attrs["rows_in_file"] = rows_in_file
    return df


def get_data():
    """Loads the data for a page, or shows a clear error and stops the page."""
    try:
        return load_data()
    except DataUnavailable as problem:
        st.error(
            "**CrashLens couldn't load its crash data.** "
            f"{problem} The app needs `data/ct_crashes_sample.csv` next to `app.py`."
        )
        st.stop()


# ---------------------------------------------------------------------------
# Coverage facts, read from the data instead of typed by hand
# ---------------------------------------------------------------------------
@st.cache_data
def get_coverage(_df):
    months = sorted(int(m) for m in _df["Month"].dropna().unique() if 1 <= int(m) <= 12)
    towns = sorted(_df["Town Name"].dropna().astype(str).str.strip().str.title().unique())
    return {
        "towns": towns,
        "towns_text": ", ".join(towns) + ", CT" if towns else "Connecticut",
        "months": months,
        "crashes": len(_df),
        "rows_in_file": _df.attrs.get("rows_in_file", len(_df)),
        "unknown_severity": int((~_df["severity_known"]).sum()),
        "with_cross_road": int((_df["cross_key"] != "").sum()),
    }


@st.cache_data
def town_options(_df):
    return sorted(_df["Town Name"].dropna().astype(str).str.strip().str.title().unique())


def _display_names(names, keys):
    """For each normalized key, the most common spelling in the data, title-cased."""
    pairs = pd.DataFrame({"name": names.fillna("").astype(str).str.strip(), "key": keys})
    pairs = pairs[pairs["key"] != ""]
    if pairs.empty:
        return {}
    best = pairs.groupby("key")["name"].agg(lambda s: s.value_counts().index[0])
    return {key: name.title() for key, name in best.items()}


@st.cache_data
def road_options(_df, town):
    """Roads in a town, most crashes first, as display names."""
    town_df = _df[_df["town_key"] == normalize_town(town)]
    names = _display_names(town_df["Roadway Name"], town_df["road_key"])
    counts = town_df["road_key"].value_counts()
    return [names[k] for k in counts.index if k in names]


@st.cache_data
def cross_road_options(_df, town, road):
    """Roads recorded as crossing `road` in either column, as display names."""
    town_df = _df[_df["town_key"] == normalize_town(town)]
    key = normalize_road_input(road)
    as_main = town_df[town_df["road_key"] == key]
    as_cross = town_df[town_df["cross_key"] == key]
    names = {}
    names.update(_display_names(as_cross["Roadway Name"], as_cross["road_key"]))
    names.update(_display_names(as_main["Intersecting Roadway Name"], as_main["cross_key"]))
    names.pop(key, None)
    return sorted(names.values())


# ---------------------------------------------------------------------------
# CrashScore comparison baseline
# ---------------------------------------------------------------------------
@st.cache_data
def get_comparison_baseline(_df):
    """
    Comparison universe for CrashScore v0.1: every Town + Road combination
    in the loaded data, using the SAME normalized names as the search. That
    keeps every searched location inside the baseline, so no component can
    go above 100. See priority_score.py for how the score works.

    Returns (highest_crash_count, highest_raw_severity).
    """
    road_level = _df[_df["road_key"] != ""].groupby(["town_key", "road_key"]).agg(
        crash_count=("CrashId", "count"),
        injury_crashes=("is_injury", "sum"),
        fatal_crashes=("is_fatal", "sum"),
    )
    if road_level.empty:
        return 0, 0
    raw_severity = calculate_raw_severity(road_level["injury_crashes"], road_level["fatal_crashes"])
    return int(road_level["crash_count"].max()), int(raw_severity.max())


DIRECTIONS = {"N": "northbound", "S": "southbound", "E": "eastbound", "W": "westbound"}
ROUTE_PREFIX = {"interstate": "I-", "usroute": "US Route ", "state": "Route "}


@st.cache_data
def route_labels(_df):
    """
    State-highway codes like "5-S" become readable names like
    "US Route 5 southbound", using the Route Class column in the data.
    Returns {road_key: readable name} for those roads only.
    """
    if "Route Class Text Format" not in _df.columns:
        return {}
    labels = {}
    codes = _df[_df["Roadway Name"].astype(str).str.strip().str.match(r"^\d+[A-Za-z]?-[NSEWnsew]$")]
    for key, group in codes.groupby("road_key"):
        number, direction = key.upper().rsplit("-", 1)
        route_class = group["Route Class Text Format"].dropna().astype(str).str.lower().str.replace(" ", "")
        prefix = ROUTE_PREFIX.get(route_class.mode().iloc[0], "Route ") if len(route_class) else "Route "
        labels[key] = f"{prefix}{number} {DIRECTIONS[direction]}"
    return labels


def readable_road(df, name):
    """The readable name for a road, e.g. "5-S" -> "US Route 5 southbound"; other names are title-cased."""
    if not isinstance(name, str) or not name.strip():
        return ""
    return route_labels(df).get(normalize_road_input(name), name.strip().title())


@st.cache_data
def rank_roads(_df, cache_key="all"):
    """
    Every Town + Road in the data, scored with the unchanged CrashScore
    and sorted highest first. Ties are broken by Severity, then crash count.
    Returns a DataFrame with one row per road.
    """
    highest_crash_count, highest_raw_severity = get_comparison_baseline(_df)
    located = _df[_df["road_key"] != ""]
    names = _display_names(located["Roadway Name"], located["road_key"])
    town_names = _display_names(located["Town Name"], located["town_key"])
    grouped = located.groupby(["town_key", "road_key"]).agg(
        crashes=("CrashId", "count"),
        injury=("is_injury", "sum"),
        fatal=("is_fatal", "sum"),
    ).reset_index()

    rows = []
    for row in grouped.itertuples(index=False):
        score = score_intersection(int(row.crashes), int(row.injury), int(row.fatal),
                                   highest_crash_count, highest_raw_severity)
        rows.append({
            "town_key": row.town_key,
            "road_key": row.road_key,
            "town": town_names.get(row.town_key, row.town_key.title()),
            "road": names.get(row.road_key, row.road_key.title()),
            "label": route_labels(_df).get(row.road_key, names.get(row.road_key, row.road_key.title())),
            "crashes": int(row.crashes),
            "injury": int(row.injury),
            "fatal": int(row.fatal),
            "frequency": score["frequency"],
            "severity": score["severity"],
            "priority": score["priority"],
        })
    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return ranking
    ranking = ranking.sort_values(["priority", "severity", "crashes"], ascending=False).reset_index(drop=True)
    ranking.insert(0, "rank", range(1, len(ranking) + 1))
    return ranking


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def find_matching_crashes(df, town, road, road_b=""):
    """
    Filters df down to crashes matching a town + road (+ optional
    intersecting road, order-independent). Used by both the single
    search and the compare page so the matching logic only lives once.
    """
    town_match = df["town_key"] == normalize_town(town)
    a = normalize_road_input(road)
    b = normalize_road_input(road_b or "")

    if b == "":
        road_match = df["road_key"] == a
    else:
        # Order-independent: "Road A x Road B" and "Road B x Road A" are the same intersection.
        forward = (df["road_key"] == a) & (df["cross_key"] == b)
        reverse = (df["road_key"] == b) & (df["cross_key"] == a)
        road_match = forward | reverse

    return df[town_match & road_match]


def explain_no_match(df, town, road, road_b=""):
    """A plain-English reason a search found nothing, with a suggestion."""
    town_key = normalize_town(town)
    towns = town_options(df)
    if town_key not in set(df["town_key"]):
        close = difflib.get_close_matches(town.strip().title(), towns, n=1, cutoff=0.6)
        hint = f" Did you mean **{close[0]}**?" if close else ""
        return (f"CrashLens doesn't have crash records for **{town.strip().title()}**.{hint} "
                f"The current data covers: {', '.join(towns)}.")

    roads = road_options(df, town)
    road_keys = {normalize_road_input(r) for r in roads}
    if normalize_road_input(road) not in road_keys:
        close = difflib.get_close_matches(road.strip().title(), roads, n=3, cutoff=0.6)
        hint = f" Similar roads in the data: {', '.join(f'**{c}**' for c in close)}." if close else ""
        return f"No crashes on **{road.strip().title()}** were found in {town.strip().title()}.{hint}"

    if road_b and road_b.strip():
        if normalize_road_input(road_b) not in road_keys:
            close = difflib.get_close_matches(road_b.strip().title(), roads, n=3, cutoff=0.6)
            hint = f" Similar roads: {', '.join(f'**{c}**' for c in close)}." if close else ""
            return f"No road named **{road_b.strip().title()}** was found in {town.strip().title()}.{hint}"
        road_total = len(find_matching_crashes(df, town, road))
        return (f"No crash records list **{road.strip().title()}** and **{road_b.strip().title()}** together. "
                f"Only some records include an intersecting road, so try searching **{road.strip().title()}** "
                f"on its own ({road_total} crash{'es' if road_total != 1 else ''} on record).")

    return "No matching crashes were found."


def location_label(town, road, road_b="", df=None):
    """Heading for a location, e.g. "Buckland Rd × Deming St". Pass df to show readable route names."""
    def name(text):
        return readable_road(df, text) if df is not None else text.strip().title()
    label = name(road)
    if road_b and road_b.strip():
        label += f" × {name(road_b)}"
    return label


def score_location(df, town, road, road_b, highest_crash_count, highest_raw_severity):
    """
    Finds a location's matching crashes and returns everything a page
    needs to display it: the matching records plus the score breakdown.
    """
    matching_df = find_matching_crashes(df, town, road, road_b)
    injury_df = matching_df[matching_df["is_injury"]]
    fatal_df = matching_df[matching_df["is_fatal"]]
    unknown_count = int((~matching_df["severity_known"]).sum())

    score = score_intersection(
        len(matching_df), len(injury_df), len(fatal_df),
        highest_crash_count, highest_raw_severity,
    )
    return {
        "matching_df": matching_df,
        "injury_df": injury_df,
        "fatal_df": fatal_df,
        "unknown_count": unknown_count,
        **score,
    }


# ---------------------------------------------------------------------------
# Location picker (used by Search and Compare)
# ---------------------------------------------------------------------------
def _pick(label, options, saved, key, placeholder, help_text=None, format_func=str):
    options = list(options)
    if saved and saved not in options:
        options = [saved] + options  # keep whatever the user typed last time
    index = options.index(saved) if saved in options else None
    return st.selectbox(
        label, options, index=index, key=key, placeholder=placeholder,
        accept_new_options=True, help=help_text, format_func=format_func,
    )


def location_inputs(df, key_prefix, saved=None):
    """
    Town, road and optional intersecting road. Each box suggests names that
    exist in the data (so searches match), but any text can still be typed.
    Returns (town, road, road_b) as strings ("" when empty).
    """
    saved = saved or {}
    towns = town_options(df)
    default_town = saved.get("town") or (towns[0] if len(towns) == 1 else None)

    town = _pick("Town", towns, default_town, f"{key_prefix}_town", "Choose or type a Connecticut town") or ""

    def show(name):
        return readable_road(df, name) or name

    road = _pick(
        "Road", road_options(df, town) if town else [], saved.get("road"), f"{key_prefix}_road",
        "Choose or type a road", "Roads are listed with the most crash records first.", show,
    ) or ""
    road_b = _pick(
        "Intersecting road (optional)", cross_road_options(df, town, road) if road else [],
        saved.get("road_b"), f"{key_prefix}_road_b", "Optional: narrow to one intersection",
        "Only roads recorded as crossing the first road are suggested.", show,
    ) or ""
    return town, road, road_b


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def calculate_percentage(part, total):
    """Percentage, or None when there is nothing to divide by (never a fake 0%)."""
    if total > 0:
        return (part / total) * 100
    return None


def plural(count, singular, plural_word):
    """plural(1, "crash", "crashes") -> "1 crash"; plural(3, ...) -> "3 crashes"."""
    return f"{count} {singular if count == 1 else plural_word}"


# Map colors for one crash, from its cleaned severity code.
SEVERITY_COLORS = {
    "fatal": [165, 15, 21],     # dark red
    "injury": [242, 140, 40],   # orange
    "none": [49, 130, 189],     # blue
    "unknown": [150, 150, 150], # gray
}


def severity_group(code):
    if code == "K":
        return "fatal"
    if code in INJURY_CODES:
        return "injury"
    if code == "O":
        return "none"
    return "unknown"


def severity_color(code):
    return SEVERITY_COLORS[severity_group(code)]
