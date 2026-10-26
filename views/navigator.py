import math
import time

import pandas as pd
import pydeck as pdk
import streamlit as st

from charts import crash_type_chart
from routing import (
    ALERT_SCORE,
    DETOUR_MAX_EXTRA_SECONDS,
    DETOUR_MAX_RATIO,
    GOOGLE_MAPS_WAYPOINTS,
    RoutingError,
    detour_points,
    distance_to_route,
    get_route_via,
    get_routes,
    google_maps_url,
    overlap_share,
    pick_suggested_route,
    points_along,
    search_place_pair,
)
from shared import GROWTH_NOTE, SCOPE_NOTE, get_coverage, get_data, plural, rank_roads, severity_color
from ui import BRAND, ENDPOINT_COLORS, esc, footer, html_block, map_legend, stat_tiles

df = get_data()
coverage = get_coverage(df)
# Crashes without a map location can't be placed near a route.
located_df = df.dropna(subset=["Latitude", "Longitude"])

MAX_ROUTES = 3
BRAND_RGB = [int(BRAND[i:i + 2], 16) for i in (1, 3, 5)]
OTHER_ROUTE_RGB = [150, 150, 150]


DATA_AREA = (located_df["Latitude"].min(), located_df["Latitude"].max(),
             located_df["Longitude"].min(), located_df["Longitude"].max())


@st.cache_data(show_spinner=False, ttl="1h")  # forget lookups after an hour
def find_places(text_a, text_b):
    """Matching places for both boxes. Cached so the same search isn't sent twice."""
    return search_place_pair(text_a, text_b, near=DATA_AREA)


@st.cache_data(show_spinner=False, ttl="1h")  # forget lookups after an hour
def look_up_detours(place_a, place_b, fastest_points, spot):
    """
    Routes from A to B through points on either side of a trouble spot on the fastest route.
    One request per point, a second apart, to go easy on the free routing service. Cached.
    """
    detours = []
    for number, via in enumerate(detour_points(list(fastest_points), spot)):
        if number:
            time.sleep(1.0)
        route = get_route_via((place_a[0], place_a[1]), via, (place_b[0], place_b[1]))
        if route:
            detours.append(route)
    return detours


@st.cache_data(show_spinner=False, ttl="1h")  # forget lookups after an hour
def look_up_routes(place_a, place_b):
    """Fetch the routes between two chosen places. Cached so moving the slider doesn't re-call the web service."""
    return {"a": place_a, "b": place_b, "routes": get_routes((place_a[0], place_a[1]), (place_b[0], place_b[1]))}


def share_inside_data_area(points):
    """How much of a route lies inside the area CrashLens has crash records for (0 to 1)."""
    margin = 0.01
    lat_low, lat_high = located_df["Latitude"].min() - margin, located_df["Latitude"].max() + margin
    lon_low, lon_high = located_df["Longitude"].min() - margin, located_df["Longitude"].max() + margin
    inside = sum(1 for lat, lon in points if lat_low <= lat <= lat_high and lon_low <= lon <= lon_high)
    return inside / len(points)


def minutes(seconds):
    return max(1, round(seconds / 60))


html_block(f"""<div class="cl-hero">
    <h1>Find a safer route.</h1>
    <p>Navigator helps teen drivers and their parents find safer routes, ones with fewer recorded crashes,
    using real police crash records. When the fastest route passes a road with a heavy crash history, it
    suggests a better one and opens it in Google Maps with one tap.</p>
    <ol class="cl-steps">
      <li><b>1</b><div>Enter where you're going<span>Type a start and a destination, then pick the right match.</span></div></li>
      <li><b>2</b><div>Compare the routes<span>See the crashes recorded along each one, and which roads score high.</span></div></li>
      <li><b>3</b><div>Drive the better route<span>Open it in Google Maps with one tap.</span></div></li>
    </ol></div>""")
st.info(f"**Coverage:** {SCOPE_NOTE} Crashes on parts of a route outside South Windsor aren't counted yet. {GROWTH_NOTE}")

address_a = st.text_input("Point A (start)", placeholder="e.g. 1540 Sullivan Ave, South Windsor", key="report_address_a")
address_b = st.text_input("Point B (destination)", placeholder="e.g. South Windsor High School", key="report_address_b")
st.caption("Type part of an address or a place name, then press **Find addresses** and pick the right match.")

if st.button("Find addresses", width="stretch"):
    if address_a.strip() == "" or address_b.strip() == "":
        st.warning("Please enter both a start and a destination.")
    else:
        try:
            with st.spinner("Looking up addresses..."):
                matches_a, matches_b = find_places(address_a.strip(), address_b.strip())
            st.session_state["address_matches"] = {"query": (address_a, address_b), "a": matches_a, "b": matches_b}
        except RoutingError as problem:
            st.error(str(problem))

matches = st.session_state.get("address_matches")
ready = False
if matches and matches["query"] != (address_a, address_b):
    st.info("You changed an address. Press **Find addresses** again to update the matches.")
elif matches:
    for letter, found_places, typed in [("A", matches["a"], address_a), ("B", matches["b"], address_b)]:
        if not found_places:
            st.warning(f"No matches for Point {letter} (\"{typed.strip()}\"). Try adding the street number, "
                       "the town, or a well-known place name.")
    if matches["a"] and matches["b"]:
        def short_name(place):
            return ", ".join(place[2].split(", ")[:3])  # "1540 Sullivan Avenue, South Windsor, Hartford County"
        place_a = st.selectbox("Choose the start", matches["a"], format_func=short_name, key="pick_a")
        place_b = st.selectbox("Choose the destination", matches["b"], format_func=short_name, key="pick_b")
        ready = True

radius = st.slider("How close to a route counts as \"along the route\" (meters)", min_value=10, max_value=100, value=30, step=5)

if ready and st.button("Generate report", type="primary", width="stretch"):
    if (place_a[0], place_a[1]) == (place_b[0], place_b[1]):
        st.warning("The start and destination are the same place. Choose a different destination.")
    else:
        # Remember the trip so moving the slider doesn't make the report disappear.
        st.session_state["report_trip"] = (place_a, place_b)
        st.session_state.pop("route_choice", None)

trip = st.session_state.get("report_trip")
if not trip:
    footer(f'Town of South Windsor, CT (limited sample)')
    st.stop()

try:
    with st.spinner("Finding routes..."):
        found = look_up_routes(trip[0], trip[1])
except RoutingError as problem:
    st.error(str(problem))
    footer(f'Town of South Windsor, CT (limited sample)')
    st.stop()

# Every road's CrashScore, so each route can be checked for high-scoring roads.
ranking = rank_roads(df)
road_scores = {(r.town_key, r.road_key): (r.label, r.priority) for r in ranking.itertuples()}


def top_road(near):
    """The highest-scoring road with crashes recorded along a route: (name, score, key), or ("", 0, None)."""
    best = ("", 0.0, None)
    for key in set(zip(near["town_key"], near["road_key"])):
        name, score = road_scores.get(key, ("", 0.0))
        if score > best[1]:
            best = (name, score, key)
    return best


def summarize(route, detour=False):
    """Crash counts and the highest-scoring road along one route."""
    distances = distance_to_route(located_df["Latitude"], located_df["Longitude"], route["points"])
    near = located_df[distances <= radius]
    summary = {
        "near_df": near,
        "crashes": len(near),
        "injury": int(near["is_injury"].sum()),
        "fatal": int(near["is_fatal"].sum()),
        "miles": route["distance_meters"] / 1609.34,
        "duration_seconds": route["duration_seconds"],
        "inside": share_inside_data_area(route["points"]),
        "points": route["points"],
        "detour": detour,
    }
    summary["top_road"], summary["top_score"], summary["top_key"] = top_road(near)
    return summary


def meters_between(p, q):
    return math.hypot((p[0] - q[0]) * 111_320.0, (p[1] - q[1]) * 111_320.0 * math.cos(math.radians(p[0])))


# ---------- Crashes along every route ----------
summaries = [summarize(route) for route in found["routes"]]
fastest = summaries[0]
suggested_index = pick_suggested_route(summaries)  # None = no alternate needed

# If the fastest route passes a high-scoring road and the routing service offered nothing better,
# make our own detours around the middle of that road's crashes on the route.
tried_detours = 0
endpoint_on_hot_road = False
if suggested_index == 0:
    near_fastest = fastest["near_df"]
    town_key, road_key = fastest["top_key"]
    hot = near_fastest[(near_fastest["town_key"] == town_key) & (near_fastest["road_key"] == road_key)]
    hot_points = list(zip(hot["Latitude"], hot["Longitude"]))
    ends = [(found["a"][0], found["a"][1]), (found["b"][0], found["b"][1])]
    endpoint_on_hot_road = any(meters_between(end, p) < 500 for end in ends for p in hot_points)
    if hot_points:
        # The hot-road crash closest to the middle of the route is the spot to detour around.
        mid = fastest["points"][len(fastest["points"]) // 2]
        spot = min(hot_points, key=lambda p: meters_between(p, mid))
        with st.spinner(f"Looking for detours around {fastest['top_road']}..."):
            detours = look_up_detours(found["a"], found["b"], tuple(fastest["points"]), spot)
        tried_detours = len(detours)
        candidates = []
        for route in detours:
            not_too_long = route["duration_seconds"] <= max(fastest["duration_seconds"] * DETOUR_MAX_RATIO,
                                                             fastest["duration_seconds"] + DETOUR_MAX_EXTRA_SECONDS)
            different = overlap_share(route["points"], fastest["points"]) < 0.9
            new = all(overlap_share(route["points"], s["points"]) < 0.9 for s in summaries + candidates)
            if not_too_long and different and new:
                candidates.append(summarize(route, detour=True))
        candidates.sort(key=lambda c: (c["top_score"], c["injury"], c["crashes"], c["duration_seconds"]))
        summaries += candidates[:max(0, MAX_ROUTES - len(summaries))]
        suggested_index = pick_suggested_route(summaries)

for number, summary in enumerate(summaries):
    summary["name"] = f"Route {number + 1}"
highlight_index = suggested_index or 0  # the route drawn in red and shown in the details
suggested = summaries[highlight_index]

# ---------- 1. The trip ----------
st.divider()
st.markdown("#### Your trip")
st.caption(f"**A:** {found['a'][2]}")
st.caption(f"**B:** {found['b'][2]}")

lowest_inside = min(s["inside"] for s in summaries)
if lowest_inside == 0:
    st.warning("At least one route is entirely outside the area CrashLens has crash data for, so its counts are empty, "
               "not safe. Treat this comparison with caution.")
elif lowest_inside < 0.95:
    st.warning(f"Part of at least one route (as little as {lowest_inside:.0%} covered) is outside the area CrashLens has "
               "crash data for. Crashes there are not counted, so the comparison is incomplete.")

# ---------- 2. Route comparison and suggestion ----------
st.markdown("#### Route options")
CAUTION = ("This compares past crash records only. It does not account for traffic volume, weather or road conditions, "
           "and it is not a guarantee that one route is safer.")
if suggested_index is None:
    if fastest["top_road"]:
        light = (f"The highest-scoring road along it is {fastest['top_road']} "
                 f"(CrashScore {fastest['top_score']:.0f} / 100), which is not above {ALERT_SCORE}.")
    else:
        light = "No crashes in the data are recorded along it."
    html_block(f"""<div class="cl-part"><div class="cl-part-name">No alternate route needed.</div>
        <p>The fastest route doesn't pass any road with a CrashScore above {ALERT_SCORE}. {esc(light)}</p></div>""")
else:
    alert = (f"The fastest route passes crashes on <b>{esc(fastest['top_road'])}</b>, which has a CrashScore of "
             f"<b>{fastest['top_score']:.0f} / 100</b> (above {ALERT_SCORE}).")
    if suggested_index == 0:
        title = "High-scoring road on every route" if len(summaries) > 1 else "High-scoring road on this route"
        if endpoint_on_hot_road:
            advice = (f"Your start or destination is on {esc(fastest['top_road'])} (or right next to it), so any route has "
                      f"to use part of it. Drive that stretch with extra care.")
        elif tried_detours:
            advice = (f"CrashLens also tried detours around {esc(fastest['top_road'])}, but none avoided a high-scoring "
                      f"road without adding a lot of driving time, so the fastest route is still the best choice by crash history.")
        else:
            advice = "The routing service found no other reasonable route for this trip, so CrashLens can't suggest one."
    else:
        extra_minutes = minutes(suggested["duration_seconds"]) - minutes(fastest["duration_seconds"])
        time_note = (f"about {plural(extra_minutes, 'minute', 'minutes')} longer" if extra_minutes > 0
                     else "about the same driving time")
        if suggested["top_road"]:
            avoids = (f"Its highest-scoring road is {esc(suggested['top_road'])} "
                      f"({suggested['top_score']:.0f} / 100)")
        else:
            avoids = "No crashes in the data are recorded along it"
        detour_note = f" (a detour around {esc(fastest['top_road'])})" if suggested["detour"] else ""
        advice = (f"<b>Try {esc(suggested['name'])}</b>{detour_note} instead. {avoids}. It has "
                  f"{esc(plural(suggested['injury'], 'injury crash', 'injury crashes'))} recorded along it "
                  f"(the fastest route has {fastest['injury']}), and it is {esc(time_note)}.")
        title = "Suggested alternate route"
    html_block(f"""<div class="cl-score" style="padding-top:1rem">
        <div class="cl-score-top"><span class="cl-eyebrow">{esc(title)}</span>
        <span class="cl-badge">Based on crash history</span></div>
        <p style="font-size:1.05rem;margin-top:0.6rem">{alert}</p>
        <p style="font-size:1.05rem">{advice}</p>
        <p class="cl-fine">{esc(CAUTION)}</p></div>""")

if len(summaries) > 1:
    rows = []
    for number, s in enumerate(summaries):
        tags = []
        if number == 0:
            tags.append("fastest")
        if s["detour"]:
            tags.append("detour")
        if suggested_index and number == suggested_index:
            tags.append("suggested")
        rows.append({
            "Route": s["name"] + (f" ({', '.join(tags)})" if tags else ""),
            "Drive time": f"{minutes(s['duration_seconds'])} min",
            "Distance": f"{s['miles']:.1f} mi",
            "Highest road score": f"{s['top_score']:.0f}" + (f" ({s['top_road']})" if s["top_road"] else ""),
            "Crashes": s["crashes"],
            "Injury": s["injury"],
            "Fatal": s["fatal"],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(f"Crashes recorded within {radius} m of each route. A crash near two routes counts for both.")

# ---------- 3. Map of all routes ----------
st.markdown("#### Routes and crash locations")
all_lats = [p[0] for s in summaries for p in s["points"]]
all_lons = [p[1] for s in summaries for p in s["points"]]
span = max(max(all_lats) - min(all_lats), max(all_lons) - min(all_lons), 0.001)
zoom = max(8, min(16, 12.4 - math.log2(span / 0.02)))  # a little zoomed out so every route fits

layers = []
# Other routes first (gray, thinner) so the highlighted route draws on top.
for number, s in enumerate(summaries):
    if number != highlight_index:
        layers.append(pdk.Layer("PathLayer", data=[{"path": [[lon, lat] for lat, lon in s["points"]]}],
                                get_path="path", get_color=OTHER_ROUTE_RGB, width_min_pixels=4))
layers.append(pdk.Layer("PathLayer", data=[{"path": [[lon, lat] for lat, lon in suggested["points"]]}],
                        get_path="path", get_color=BRAND_RGB, width_min_pixels=6))

near_any = pd.concat([s["near_df"] for s in summaries]).drop_duplicates(subset="CrashId")
if len(near_any) > 0:
    crash_map = near_any[["Latitude", "Longitude", "severity_code"]].copy()
    crash_map["color"] = crash_map["severity_code"].apply(severity_color)
    layers.append(pdk.Layer("ScatterplotLayer", data=crash_map, get_position="[Longitude, Latitude]",
                            get_fill_color="color", get_radius=14, radius_min_pixels=6, stroked=True,
                            get_line_color=[255, 255, 255], line_width_min_pixels=1))

ends = pd.DataFrame([
    {"lat": found["a"][0], "lon": found["a"][1], "color": ENDPOINT_COLORS["start"]},
    {"lat": found["b"][0], "lon": found["b"][1], "color": ENDPOINT_COLORS["end"]},
])
layers.append(pdk.Layer("ScatterplotLayer", data=ends, get_position="[lon, lat]", get_fill_color="color",
                        get_radius=22, radius_min_pixels=9, stroked=True, get_line_color=[255, 255, 255],
                        line_width_min_pixels=2))

st.pydeck_chart(pdk.Deck(
    layers=layers,
    map_style="light",
    initial_view_state=pdk.ViewState(latitude=sum(all_lats) / len(all_lats),
                                     longitude=sum(all_lons) / len(all_lons), zoom=zoom),
), height=380)
if len(summaries) > 1:
    highlighted = "suggested alternate route" if suggested_index else "fastest route"
    st.caption(f"Red line: {highlighted}. Gray lines: other routes.")
map_legend(include_endpoints=True, include_unknown=bool((~near_any["severity_known"]).any()) if len(near_any) else False)

# ---------- 4. Details for one route ----------
st.markdown("#### Route details")
if len(summaries) > 1:
    choice = st.radio("Show details for", [s["name"] for s in summaries], index=highlight_index,
                      horizontal=True, key="route_choice")
    detail = next(s for s in summaries if s["name"] == choice)
else:
    detail = summaries[0]

# ---------- Navigate in Google Maps ----------
is_fastest = detail is summaries[0]
# The fastest route needs no waypoints; an alternate gets 3 points along it so Google follows the same roads.
waypoints = [] if is_fastest else points_along(detail["points"], GOOGLE_MAPS_WAYPOINTS)
nav_url = google_maps_url((found["a"][0], found["a"][1]), (found["b"][0], found["b"][1]), waypoints)
st.link_button(f"Navigate {detail['name']} in Google Maps", nav_url, type="primary", width="stretch",
               icon=":material/navigation:")
if waypoints:
    st.caption("Opens Google Maps with 3 points along this route so it follows the same roads. Google may list them "
               "as stops; you can drive straight through. Set up directions before you start driving.")
else:
    st.caption("Opens Google Maps with this trip. Google may pick a slightly different fastest route based on "
               "live traffic. Set up directions before you start driving.")

stat_tiles([
    ("Distance", f"{detail['miles']:.1f} mi", f"about {minutes(detail['duration_seconds'])} min"),
    ("Crashes", detail["crashes"], f"within {radius} m"),
    ("Injury crashes", detail["injury"], f"{detail['fatal']} fatal"),
])

if detail["crashes"] > 0:
    crash_type_chart(detail["near_df"])
else:
    st.info("No crashes in the data fall within that distance of this route.")

# ---------- 5. Read this first ----------
st.divider()
st.markdown("#### About Navigator")
st.write("Navigator counts historical crash records located near driving routes. It is not a prediction, a safety "
         "rating, or a guarantee about which route is safer.")
with st.expander("Limitations"):
    st.markdown(
        """
- This version uses a limited sample of crash records for the Town of South Windsor only, so crashes elsewhere aren't counted yet.
- Routes come from a free routing service. It only offers alternatives that are reasonably direct, so short trips often have just one route.
- An alternate is suggested only when the fastest route passes crashes on a road with a CrashScore above {alert} (out of 100). The suggestion is the route whose highest-scoring road is lowest, then the one with the fewest injury crashes. It does not consider traffic volume: a busy road naturally has more crashes than a quiet one.
- When the routing service offers only one route, CrashLens tries up to four detours through points about 0.4 and 0.9 miles to either side of the high-scoring road. A detour can only use roads that exist there, so sometimes none helps.
- A road counts as "on the route" when one of its crashes is recorded within the distance you chose, so a crash on a cross street right at an intersection can flag that cross street.
- A crash counts as "along the route" if its recorded location is within the distance you chose. Crash locations are not perfectly precise, so nearby side-street crashes can be included and some on-route crashes missed.
- Addresses you type are sent to OpenStreetMap (Nominatim) to be located and to the public OSRM server to find routes. The Google Maps button sends only the start, destination and route points to Google, and only when you press it.
        """.format(alert=ALERT_SCORE)
    )

with st.expander(f"See the {plural(len(detail['near_df']), 'crash record', 'crash records')} along {detail['name']}"):
    st.dataframe(detail["near_df"].drop(columns=["town_key", "road_key", "cross_key", "severity_code", "is_injury",
                                                 "is_fatal", "severity_known"]), hide_index=True, width="stretch")

footer(f'Town of South Windsor, CT (limited sample)')
