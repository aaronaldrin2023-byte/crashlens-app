"""
Routing helpers for the Safety Report (A to B).

Steps:
  1. search_places()       address text -> up to 5 matching places to pick from (OpenStreetMap Nominatim)
     geocode()             address text -> the single best match
  2. get_routes()          two points   -> the fastest driving route plus any alternatives (OSRM public server)
  3. distance_to_route()   how far each crash is from a route line, in meters
  4. pick_suggested_route() whether to suggest an alternate, and which one

Both web services are free, keyless, and best-effort. The addresses a user
types are sent to them. Nothing else about the user is.
"""
import time
from urllib.parse import urlencode

import numpy as np
import requests

HEADERS = {"User-Agent": "CrashLens-student-project/0.1 (Congressional App Challenge)"}
TIMEOUT_SECONDS = 20

# Detours CrashLens builds itself when the routing service offers nothing better:
# points this many meters to each side of the high-scoring road (about 0.4 and 0.9 miles),
# keeping detours at most 60% longer than the fastest route (or 5 minutes, whichever is more).
DETOUR_OFFSETS_METERS = (700, -700, 1400, -1400)
DETOUR_MAX_RATIO = 1.6
DETOUR_MAX_EXTRA_SECONDS = 300
GOOGLE_MAPS_WAYPOINTS = 3  # the most Google Maps allows in phone browsers


class RoutingError(Exception):
    """A problem we can explain to the user in plain English."""


def search_places(text, limit=5, near=None):
    """
    Up to `limit` places matching the text, best first, as (latitude, longitude, name).
    `near` = (lat_low, lat_high, lon_low, lon_high) prefers places in that box
    (CrashLens passes the area its crash data covers) without excluding others.

    Called once per button press, never while typing: OpenStreetMap's Nominatim
    usage policy forbids search-as-you-type autocomplete.
    """
    if text.strip() == "":
        return []
    params = {"q": text, "format": "json", "limit": limit, "countrycodes": "us"}
    if near:
        lat_low, lat_high, lon_low, lon_high = near
        params["viewbox"] = f"{lon_low},{lat_high},{lon_high},{lat_low}"  # left, top, right, bottom
    try:
        response = requests.get("https://nominatim.openstreetmap.org/search", params=params,
                                headers=HEADERS, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError):
        raise RoutingError("The address lookup service couldn't be reached. Check your internet connection and try again.")
    return [(float(r["lat"]), float(r["lon"]), r["display_name"]) for r in results]


def search_place_pair(text_a, text_b, near=None):
    """Looks up both boxes, pausing between calls (Nominatim allows 1 request per second)."""
    a = search_places(text_a, near=near)
    time.sleep(1.1)
    b = search_places(text_b, near=near)
    return a, b


def geocode(address):
    """Returns (latitude, longitude, resolved_name) or raises RoutingError."""
    if address.strip() == "":
        raise RoutingError("Please enter an address.")
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "us"},
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        results = response.json()
    except requests.RequestException:
        raise RoutingError("The address lookup service couldn't be reached. Check your internet connection and try again.")
    if not results:
        raise RoutingError(f"Couldn't find the address \"{address}\". Try adding the town and state, like \"1540 Sullivan Ave, South Windsor, CT\".")
    top = results[0]
    return float(top["lat"]), float(top["lon"]), top["display_name"]


def get_routes(start, end, max_routes=3):
    """
    start and end are (latitude, longitude).
    Asks OSRM for the main driving route plus up to two alternatives.
    Returns a list (fastest first) of dicts:
        {"points": [(lat, lon), ...], "distance_meters": float, "duration_seconds": float}
    OSRM only returns alternatives that are reasonably different and not much
    longer, so for many short trips the list has just one route.
    """
    url = f"https://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}"
    try:
        response = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson", "alternatives": str(max_routes - 1)},
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
        data = response.json()
    except (requests.RequestException, ValueError):
        raise RoutingError("The routing service couldn't be reached. Check your internet connection and try again.")
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError("No driving route was found between those two points.")
    routes = []
    for route in data["routes"][:max_routes]:
        # GeoJSON stores points as [longitude, latitude]; we flip to (latitude, longitude).
        points = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
        if len(points) >= 2:
            routes.append({
                "points": points,
                "distance_meters": float(route["distance"]),
                "duration_seconds": float(route.get("duration", 0.0)),
            })
    if not routes:
        raise RoutingError("No driving route was found between those two points.")
    return routes


def get_route_via(start, via, end):
    """
    The fastest route from start to end that passes through `via` (all (latitude, longitude)).
    Returns one route dict like get_routes(), or None if the routing service can't make one.
    """
    coords = ";".join(f"{lon},{lat}" for lat, lon in (start, via, end))
    try:
        response = requests.get(
            f"https://router.project-osrm.org/route/v1/driving/{coords}",
            params={"overview": "full", "geometries": "geojson"},
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS,
        )
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    route = data["routes"][0]
    points = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
    if len(points) < 2:
        return None
    return {"points": points, "distance_meters": float(route["distance"]),
            "duration_seconds": float(route.get("duration", 0.0))}


def detour_points(route_points, spot, offsets_meters=DETOUR_OFFSETS_METERS):
    """
    Points to the left and right of a route at `spot` (latitude, longitude): each
    offset is measured at a right angle to the route's direction there
    (positive = left of travel). Routing through one of them makes a detour
    around that spot.
    """
    route = np.array(route_points, dtype=float)
    if len(route) < 2:
        return []
    lat0 = float(route[:, 0].mean())
    m_lat, m_lon = 111_320.0, 111_320.0 * np.cos(np.radians(lat0))
    xy = np.column_stack([(route[:, 1] - route[0, 1]) * m_lon, (route[:, 0] - route[0, 0]) * m_lat])
    spot_xy = np.array([(spot[1] - route[0, 1]) * m_lon, (spot[0] - route[0, 0]) * m_lat])
    nearest = int(np.argmin(((xy - spot_xy) ** 2).sum(axis=1)))
    # Direction of travel around the spot, from a few points before to a few after.
    before, after = max(nearest - 5, 0), min(nearest + 5, len(route) - 1)
    direction = xy[after] - xy[before]
    if not np.any(direction):
        direction = xy[-1] - xy[0]
    length = float(np.hypot(*direction))
    if length == 0:
        return []
    left = np.array([-direction[1], direction[0]]) / length  # 90 degrees to the left of travel
    points = []
    for offset in offsets_meters:
        x, y = xy[nearest] + left * offset
        points.append((round(float(route[0, 0] + y / m_lat), 6), round(float(route[0, 1] + x / m_lon), 6)))
    return points


def overlap_share(route_a, route_b, within_meters=30):
    """Share (0 to 1) of route_a's points that lie within `within_meters` of route_b."""
    if len(route_a) == 0 or len(route_b) < 2:
        return 0.0
    lats = [p[0] for p in route_a]
    lons = [p[1] for p in route_a]
    return float((distance_to_route(lats, lons, route_b) <= within_meters).mean())


def get_route(start, end):
    """The single fastest route: (route_points, distance_meters)."""
    fastest = get_routes(start, end, max_routes=1)[0]
    return fastest["points"], fastest["distance_meters"]


# A route "needs an alternate" when it passes crashes on a road whose CrashScore
# is above this (the score runs 0-100, so 50 is the top half of the scale).
ALERT_SCORE = 50


def pick_suggested_route(summaries, alert_score=ALERT_SCORE):
    """
    summaries: one dict per route, fastest first, each with "top_score" (the
    highest CrashScore of any road with crashes recorded along the route),
    "injury", "crashes" and "duration_seconds".

    Returns None when the fastest route has no road above alert_score: no
    alternate is needed. Otherwise returns the index of the route with the
    lowest top_score, then the fewest injury crashes, then the fewest crashes,
    then the shortest drive. That can be 0, meaning no alternative is better.
    This only compares recorded crash history; it is not a safety rating.
    """
    if not summaries or summaries[0]["top_score"] <= alert_score:
        return None
    return min(
        range(len(summaries)),
        key=lambda i: (summaries[i]["top_score"], summaries[i]["injury"],
                       summaries[i]["crashes"], summaries[i]["duration_seconds"]),
    )


def points_along(route_points, count=3):
    """
    `count` points spread evenly along a route by distance (at 1/4, 1/2, 3/4 of the
    way for count=3), never the start or end. Used as Google Maps waypoints so
    Google follows the same roads as the route shown in CrashLens.
    """
    route = np.array(route_points, dtype=float)
    if len(route) < 2 or count < 1:
        return []
    meters_per_degree_lon = 111_320.0 * np.cos(np.radians(route[:, 0].mean()))
    steps = np.sqrt(((np.diff(route[:, 0]) * 111_320.0) ** 2) + ((np.diff(route[:, 1]) * meters_per_degree_lon) ** 2))
    along = np.concatenate([[0.0], np.cumsum(steps)])
    if along[-1] == 0:
        return []
    picks = []
    for i in range(1, count + 1):
        target = along[-1] * i / (count + 1)
        # Find the segment that contains this distance, then move partway along it.
        segment = min(int(np.searchsorted(along, target, side="right")) - 1, len(route) - 2)
        fraction = (target - along[segment]) / steps[segment] if steps[segment] > 0 else 0.0
        lat, lon = route[segment] + fraction * (route[segment + 1] - route[segment])
        picks.append((round(float(lat), 6), round(float(lon), 6)))
    return picks


def google_maps_url(start, end, waypoints=()):
    """
    A Google Maps driving-directions link (Maps URLs, no key needed).
    start and end are (latitude, longitude); waypoints is a list of (latitude, longitude).
    Google allows up to 3 waypoints in phone browsers, so we never send more.
    """
    def coords(point):
        return f"{point[0]:.6f},{point[1]:.6f}"

    params = {"api": "1", "origin": coords(start), "destination": coords(end), "travelmode": "driving"}
    if waypoints:
        params["waypoints"] = "|".join(coords(p) for p in list(waypoints)[:3])
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def geocode_pair(address_a, address_b):
    """Looks up both addresses, pausing between calls (Nominatim allows 1 request per second)."""
    a = geocode(address_a)
    time.sleep(1.1)
    b = geocode(address_b)
    return a, b


def distance_to_route(crash_lats, crash_lons, route_points):
    """
    For each crash, the distance in meters to the nearest part of the route line.

    Works by flattening latitude/longitude into meters around the route's
    center (accurate enough over a few kilometers), then finding the closest
    point on every little segment of the route.
    """
    route = np.array(route_points, dtype=float)
    lat0 = route[:, 0].mean()
    lon0 = route[:, 1].mean()
    meters_per_degree_lat = 111_320.0
    meters_per_degree_lon = 111_320.0 * np.cos(np.radians(lat0))

    def to_xy(lats, lons):
        x = (np.asarray(lons, dtype=float) - lon0) * meters_per_degree_lon
        y = (np.asarray(lats, dtype=float) - lat0) * meters_per_degree_lat
        return np.column_stack([x, y])

    points = to_xy(crash_lats, crash_lons)         # (N, 2) crashes
    route_xy = to_xy(route[:, 0], route[:, 1])     # (M+1, 2) route vertices
    seg_start = route_xy[:-1]                      # (M, 2)
    seg_vec = route_xy[1:] - seg_start             # (M, 2)
    seg_len_sq = (seg_vec ** 2).sum(axis=1)
    seg_len_sq[seg_len_sq == 0] = 1e-9             # avoid dividing by zero on repeated points

    offset = points[:, None, :] - seg_start[None, :, :]                  # (N, M, 2)
    t = (offset * seg_vec[None, :, :]).sum(axis=2) / seg_len_sq[None, :]  # position along each segment
    t = np.clip(t, 0.0, 1.0)
    closest = seg_start[None, :, :] + t[:, :, None] * seg_vec[None, :, :]
    distances = np.sqrt(((points[:, None, :] - closest) ** 2).sum(axis=2))
    return distances.min(axis=1)
