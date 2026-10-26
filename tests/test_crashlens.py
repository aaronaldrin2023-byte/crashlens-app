"""
Automated checks for CrashLens.

They use tests/fixtures/test_crashes.csv: a tiny MADE-UP file built only to
exercise edge cases (mixed spellings, reversed intersections, blank severity,
a duplicate row, a missing location). It is never shown in the app.

Run with:  python -m pytest -q
"""
import os
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "test_crashes.csv"
os.environ["CRASHLENS_DATA"] = str(FIXTURE)
APP_DIR = Path(__file__).resolve().parents[1]

import shared  # noqa: E402  (must come after CRASHLENS_DATA is set)
from priority_score import calculate_priority_score, score_intersection  # noqa: E402


@pytest.fixture(scope="module")
def df():
    return shared.load_data(str(FIXTURE))


@pytest.fixture(scope="module")
def baseline(df):
    return shared.get_comparison_baseline(df)


# ---------- CrashScore formula (unchanged from v0.1) ----------
def test_formula_weights():
    assert calculate_priority_score(60, 80) == pytest.approx(74)


def test_zero_comparison_group_does_not_divide_by_zero():
    result = score_intersection(5, 2, 1, 0, 0)
    assert result["frequency"] == 0 and result["severity"] == 0


# ---------- Data cleaning ----------
def test_duplicate_crash_ids_counted_once(df):
    assert df["CrashId"].is_unique
    assert df.attrs["rows_in_file"] == len(df) + 1


def test_blank_severity_is_unknown_not_injury(df):
    rye = shared.find_matching_crashes(df, "South Windsor", "Rye St")
    assert len(rye) == 4
    assert int(rye["is_injury"].sum()) == 1          # only the "B"
    assert int((~rye["severity_known"]).sum()) == 2  # "" and missing


# ---------- Matching ----------
def test_spelling_and_case_variants_match(df):
    a = shared.find_matching_crashes(df, "south windsor", "Buckland Road")
    b = shared.find_matching_crashes(df, "SOUTH WINDSOR", "buckland rd")
    assert len(a) == len(b) == 9


def test_intersection_is_order_independent(df):
    forward = shared.find_matching_crashes(df, "South Windsor", "Buckland Rd", "Sullivan Ave")
    reverse = shared.find_matching_crashes(df, "South Windsor", "Sullivan Avenue", "Buckland Road")
    assert len(forward) == len(reverse) == 2
    assert int(forward["is_fatal"].sum()) == 1


def test_whole_word_normalization_only():
    assert shared.normalize_road_input("Avery St") == "avery st"
    assert shared.normalize_road_input("  Main   Street ") == "main st"


# ---------- Score bounds (the bug this release fixes) ----------
def test_baseline_uses_normalized_names(df, baseline):
    highest_count, highest_severity = baseline
    assert highest_count == 9       # all Buckland spellings combined
    assert highest_severity == 16   # Sullivan Ave: 2 injury (incl. 1 fatal) -> 2*3 + 10


@pytest.mark.parametrize("road,cross", [
    ("Buckland Road", ""), ("BUCKLAND RD", ""), ("Sullivan Ave", ""), ("Rye St", ""),
    ("Buckland Rd", "Sullivan Ave"), ("Pleasant Valley Rd", ""),
])
def test_scores_stay_between_0_and_100(df, baseline, road, cross):
    result = shared.score_location(df, "South Windsor", road, cross, *baseline)
    for part in ("frequency", "severity", "priority"):
        assert 0 <= result[part] <= 100


def test_busiest_and_most_severe_values(df, baseline):
    buckland = shared.score_location(df, "South Windsor", "Buckland Rd", "", *baseline)
    assert buckland["frequency"] == pytest.approx(100)
    assert buckland["severity"] == pytest.approx(9 / 16 * 100)  # 3 injury crashes * 3 points


# ---------- Helpful messages ----------
def test_unknown_town_message(df):
    message = shared.explain_no_match(df, "Hartford", "Main St")
    assert "doesn't have crash records for **Hartford**" in message


def test_unknown_road_suggests_similar(df):
    message = shared.explain_no_match(df, "South Windsor", "Bucklnd Rd")
    assert "Buckland Rd" in message


def test_missing_intersection_suggests_road_alone(df):
    message = shared.explain_no_match(df, "South Windsor", "Rye St", "Buckland Rd")
    assert "on its own" in message


def test_percentage_is_none_not_zero_when_no_data():
    assert shared.calculate_percentage(3, 0) is None


# ---------- Pages start without errors (Streamlit's own test runner) ----------
def run_page(path, search=None):
    from streamlit.testing.v1 import AppTest
    # Pages run through app.py, like in the real app, so navigation links work.
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    if search is not None:
        at.session_state["search"] = search
    at.run()
    if path != "views/navigator.py":  # Navigator is the first page
        at.switch_page(path)
        at.run()
    return at


@pytest.mark.parametrize("page", ["views/home.py", "views/compare.py",
                                  "views/navigator.py", "views/search_results.py"])
def test_page_runs_without_exceptions(page):
    os.chdir(APP_DIR)
    at = run_page(page)
    assert not at.exception, at.exception


def test_results_page_shows_score(monkeypatch):
    os.chdir(APP_DIR)
    at = run_page("views/search_results.py", {"town": "South Windsor", "road": "Buckland Road", "road_b": ""})
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "cl-score-value" in html and ">69<" in html  # 0.3 x 100 + 0.7 x 56.25 = 69.4


def test_results_page_unknown_town_warns():
    os.chdir(APP_DIR)
    at = run_page("views/search_results.py", {"town": "Hartford", "road": "Main St", "road_b": ""})
    assert not at.exception
    assert any("Hartford" in w.value for w in at.warning)


# ---------- Real data checks (skipped if the real CSV isn't present) ----------
REAL = APP_DIR / "data" / "ct_crashes_sample.csv"
needs_real = pytest.mark.skipif(not REAL.exists(), reason="real crash data not present")


@pytest.fixture
def real():
    # Cached helpers remember the test file's answers, so start fresh for the real file.
    import streamlit as st
    st.cache_data.clear()
    yield shared.load_data(str(REAL))
    st.cache_data.clear()


@needs_real
def test_real_buckland_matches_hand_calculation(real):
    highest = shared.get_comparison_baseline(real)
    assert highest == (22, 30)  # 5-S has the most crashes; 30 is the highest severity points
    r = shared.score_location(real, "South Windsor", "Buckland Road", "", *highest)
    assert (r["crash_count"], r["injury_crashes"], r["fatal_crashes"]) == (18, 5, 0)
    assert r["priority"] == pytest.approx(0.3 * 18 / 22 * 100 + 0.7 * 15 / 30 * 100)


@needs_real
def test_real_every_road_scores_between_0_and_100(real):
    highest = shared.get_comparison_baseline(real)
    for road in real["Roadway Name"].unique():
        r = shared.score_location(real, "South Windsor", road, "", *highest)
        assert len(r["matching_df"]) > 0
        assert 0 <= r["priority"] <= 100


def test_ranking_sorted_and_complete(df):
    ranking = shared.rank_roads(df, "fixture")
    assert list(ranking["rank"]) == list(range(1, len(ranking) + 1))
    assert ranking["priority"].is_monotonic_decreasing
    assert ranking.iloc[0]["road"] == "Sullivan Ave"  # the fatal crash makes Severity 100 (score 80 vs 69)


@needs_real
def test_real_ranking_top_is_route_5_south(real):
    ranking = shared.rank_roads(real, "real")
    assert ranking.iloc[0]["label"] == "US Route 5 southbound"
    assert ranking.iloc[0]["priority"] == pytest.approx(100)
    buckland = ranking[ranking["road"] == "Buckland Rd"].iloc[0]
    assert buckland["rank"] == 6


# ---------- Alternate route suggestion (simulated routes; no internet needed) ----------
import routing  # noqa: E402


def test_no_alternate_when_fastest_route_is_at_or_below_50():
    routes = [{"top_score": 50, "injury": 3, "crashes": 9, "duration_seconds": 600},
              {"top_score": 0, "injury": 0, "crashes": 0, "duration_seconds": 700}]
    assert routing.pick_suggested_route(routes) is None


def test_alternate_picks_lowest_top_score_then_injuries():
    routes = [
        {"top_score": 60, "injury": 2, "crashes": 3, "duration_seconds": 600},
        {"top_score": 30, "injury": 1, "crashes": 5, "duration_seconds": 700},
        {"top_score": 30, "injury": 0, "crashes": 6, "duration_seconds": 900},
    ]
    assert routing.pick_suggested_route(routes) == 2


def test_fastest_kept_when_no_alternative_is_better():
    routes = [{"top_score": 60, "injury": 2, "crashes": 3, "duration_seconds": 600},
              {"top_score": 80, "injury": 0, "crashes": 1, "duration_seconds": 650}]
    assert routing.pick_suggested_route(routes) == 0


def fake_routes(df):
    """Route 1 passes through every Buckland Rd crash; Route 2 runs well north of all crashes."""
    buckland = shared.find_matching_crashes(df, "South Windsor", "Buckland Rd").sort_values("Latitude")
    through_crashes = list(zip(buckland["Latitude"], buckland["Longitude"]))
    away = [(41.95, -72.60), (41.95, -72.55)]
    return [
        {"points": through_crashes, "distance_meters": 3000.0, "duration_seconds": 300.0},
        {"points": away, "distance_meters": 4200.0, "duration_seconds": 420.0},
    ]


def test_route_report_suggests_alternate(monkeypatch, df):
    import streamlit as st
    st.cache_data.clear()
    places = ((41.83, -72.57, "Start, South Windsor"), (41.85, -72.57, "End, South Windsor"))
    monkeypatch.setattr(routing, "get_routes", lambda start, end, max_routes=3: fake_routes(df))
    os.chdir(APP_DIR)
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    at.session_state["report_trip"] = places
    at.run()
    at.switch_page("views/navigator.py")
    at.run()
    assert not at.exception, at.exception
    page = " ".join(m.value for m in at.markdown)
    # Buckland Rd scores 69 in the test file, above 50, so Route 2 is suggested.
    assert "Suggested alternate route" in page and "Try Route 2" in page
    assert "Buckland Rd" in page and "about 2 minutes longer" in page
    st.cache_data.clear()


def test_route_report_says_no_alternate_needed_for_low_scores(monkeypatch, df):
    import streamlit as st
    st.cache_data.clear()
    rye = shared.find_matching_crashes(df, "South Windsor", "Rye St").dropna(subset=["Latitude"]).sort_values("Latitude")
    lat, lon = rye["Latitude"].iloc[0], rye["Longitude"].iloc[0]  # a short route past one Rye St crash only
    routes = [{"points": [(lat - 0.0005, lon), (lat + 0.0005, lon)], "distance_meters": 2000.0, "duration_seconds": 240.0},
              {"points": [(41.95, -72.60), (41.95, -72.55)], "distance_meters": 2500.0, "duration_seconds": 300.0}]
    places = ((41.83, -72.57, "Start"), (41.85, -72.57, "End"))
    monkeypatch.setattr(routing, "get_routes", lambda start, end, max_routes=3: routes)
    os.chdir(APP_DIR)
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    at.session_state["report_trip"] = places
    at.run()
    at.switch_page("views/navigator.py")
    at.run()
    assert not at.exception, at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "No alternate route needed" in page and "Suggested alternate route" not in page
    st.cache_data.clear()


def test_find_and_pick_addresses(monkeypatch, df):
    """Type two addresses, press Find, pick from the matches, then generate the report."""
    import streamlit as st
    st.cache_data.clear()
    calls = []

    def fake_search(text_a, text_b, near=None):
        calls.append((text_a, text_b))
        return ([(41.83, -72.57, "1540 Sullivan Ave, South Windsor"), (41.70, -72.60, "Sullivan Ave, Somewhere Else")],
                [(41.85, -72.57, "South Windsor High School")])

    monkeypatch.setattr(routing, "search_place_pair", fake_search)
    monkeypatch.setattr(routing, "get_routes", lambda start, end, max_routes=3: fake_routes(df))
    os.chdir(APP_DIR)
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    at.run()
    at.switch_page("views/navigator.py")
    at.run()
    at.text_input(key="report_address_a").input("1540 Sullivan")
    at.text_input(key="report_address_b").input("SWHS")
    at.button[0].click()  # Find addresses
    at.run()
    assert not at.exception, at.exception
    assert calls == [("1540 Sullivan", "SWHS")]
    assert len(at.selectbox(key="pick_a").options) == 2
    next(b for b in at.button if b.label == "Generate report").click()
    at.run()
    assert not at.exception, at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "Route options" in page
    st.cache_data.clear()


def test_points_along_and_google_maps_url():
    route = [(41.80, -72.57), (41.82, -72.57), (41.84, -72.57), (41.86, -72.57), (41.88, -72.57)]
    picks = routing.points_along(route, 3)
    assert len(picks) == 3 and picks[0] != route[0] and picks[-1] != route[-1]
    url = routing.google_maps_url((41.80, -72.57), (41.88, -72.57), picks)
    assert url.startswith("https://www.google.com/maps/dir/?api=1&origin=41.800000%2C-72.570000")
    assert "travelmode=driving" in url and url.count("%7C") == 2  # 3 waypoints, pipe-separated
    assert "waypoints" not in routing.google_maps_url((41.80, -72.57), (41.88, -72.57))


def test_route_report_navigates_suggested_route(monkeypatch, df):
    import streamlit as st
    st.cache_data.clear()
    places = ((41.83, -72.57, "Start"), (41.85, -72.57, "End"))
    monkeypatch.setattr(routing, "get_routes", lambda start, end, max_routes=3: fake_routes(df))
    os.chdir(APP_DIR)
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    at.session_state["report_trip"] = places
    at.run()
    at.switch_page("views/navigator.py")
    at.run()
    assert not at.exception, at.exception
    buttons = at.get("link_button")
    assert len(buttons) == 1
    assert buttons[0].proto.label == "Navigate Route 2 in Google Maps"  # the suggested route is shown by default
    assert "waypoints=" in buttons[0].proto.url
    st.cache_data.clear()


# ---------- Detours when the routing service offers only one route ----------
def run_route_report(monkeypatch, df, routes, via_route, places=((41.70, -72.57, "Start"), (41.98, -72.57, "End"))):
    import streamlit as st
    st.cache_data.clear()
    calls = []
    monkeypatch.setattr(routing, "get_routes", lambda start, end, max_routes=3: routes)

    def fake_via(start, via, end):
        calls.append(via)
        return via_route
    monkeypatch.setattr(routing, "get_route_via", fake_via)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    os.chdir(APP_DIR)
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=30)
    at.session_state["report_trip"] = places
    at.run()
    at.switch_page("views/navigator.py")
    at.run()
    assert not at.exception, at.exception
    st.cache_data.clear()
    return " ".join(m.value for m in at.markdown), calls


def test_detour_found_when_only_one_route(monkeypatch, df):
    only = [fake_routes(df)[0]]  # passes every Buckland Rd crash (score 69 in the test file)
    detour = {"points": [(41.70, -72.57), (41.70, -72.65), (41.98, -72.65), (41.98, -72.57)],
              "distance_meters": 5000.0, "duration_seconds": 420.0}
    page, calls = run_route_report(monkeypatch, df, only, detour)
    assert len(calls) == 4  # four detour points tried
    assert "Suggested alternate route" in page and "a detour around Buckland Rd" in page


def test_no_detour_when_endpoint_is_on_hot_road(monkeypatch, df):
    only = [fake_routes(df)[0]]
    start = only[0]["points"][0]  # the trip starts at a Buckland Rd crash location
    page, calls = run_route_report(monkeypatch, df, only, only[0],
                                   places=((start[0], start[1], "Start on Buckland"), (41.98, -72.57, "End")))
    assert "Your start or destination is on Buckland Rd" in page
