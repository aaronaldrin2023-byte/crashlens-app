import streamlit as st

from charts import crash_type_chart, hour_chart, month_chart, weekday_chart
from priority_score import FATAL_POINTS, FREQUENCY_WEIGHT, INJURY_POINTS, SEVERITY_WEIGHT, calculate_raw_severity
from shared import (
    TYPE_COLUMN,
    calculate_percentage,
    explain_no_match,
    get_comparison_baseline,
    get_coverage,
    get_data,
    location_label,
    normalize_road_input,
    normalize_town,
    plural,
    rank_roads,
    score_location,
    severity_color,
)
from ui import esc, footer, stat_tiles, location_heading, map_legend, score_card, score_parts

df = get_data()
coverage = get_coverage(df)
highest_crash_count, highest_raw_severity = get_comparison_baseline(df)

search = st.session_state.get("search")

if not search:
    st.subheader("Results")
    st.info("No search yet. Choose a town and road on the Road Lookup page to see results here.")
    st.page_link("views/home.py", label="Go to Road Lookup", icon=":material/search:")
    st.stop()

town = search["town"]
road = search["road"]
road_b = search.get("road_b", "")
is_intersection = road_b.strip() != ""

score = score_location(df, town, road, road_b, highest_crash_count, highest_raw_severity)
matching_df = score["matching_df"]
matching_crashes = len(matching_df)
injury_crashes = len(score["injury_df"])
fatal_crashes = len(score["fatal_df"])
unknown_count = score["unknown_count"]

# ---------- 1. Location ----------
st.page_link("views/home.py", label="New search", icon=":material/arrow_back:")
label = location_label(town, road, road_b, df)
location_heading(label, f"{town.strip().title()}, CT · {'Intersection' if is_intersection else 'Whole road'}")

if matching_crashes == 0:
    st.warning(explain_no_match(df, town, road, road_b))
    st.stop()

# ---------- 2. CrashScore ----------
raw_severity = calculate_raw_severity(injury_crashes, fatal_crashes)
frequency_part = score["frequency"] * FREQUENCY_WEIGHT
severity_part = score["severity"] * SEVERITY_WEIGHT
if severity_part > frequency_part:
    driver = "Most of this score comes from the <b>severity</b> of past crashes."
elif frequency_part > severity_part:
    driver = "Most of this score comes from the <b>number</b> of past crashes."
else:
    driver = "Frequency and severity contribute equally to this score."

explanation = (
    f"{esc(label)} has <b>{plural(matching_crashes, 'crash', 'crashes')}</b> on record, "
    f"including <b>{injury_crashes} with injuries</b> and <b>{fatal_crashes} fatal</b>. {driver}"
)
fine_print = (
    "This score compares roads by their past crash records, so Navigator can steer teen drivers around the "
    "roads with the heaviest crash history. It is based only on this data. It does not predict future crashes "
    "and it is not an official safety rating."
)
score_card(score["priority"], explanation, fine_print)

if not is_intersection:
    ranking = rank_roads(df)
    here = ranking[(ranking["town"].map(normalize_town) == normalize_town(town))
                   & (ranking["road"].map(normalize_road_input) == normalize_road_input(road))]
    if len(here):
        st.markdown(f"**Ranked #{int(here['rank'].iloc[0])} of {len(ranking)} roads** in the data by CrashScore.")

if is_intersection:
    st.caption(
        "This intersection is scored against whole roads in the data, so it will usually score lower "
        "than a full road with many crashes. Compare it with other intersections for a fair comparison."
    )

st.markdown("#### Why this score?")
score_parts(
    score["frequency"],
    score["severity"],
    frequency_note=f"{plural(matching_crashes, 'crash', 'crashes')}, compared with the road that has the most crashes in the data.",
    severity_note=f"{injury_crashes} injury and {fatal_crashes} fatal, compared with the road with the most severe crash history.",
    frequency_math=f"{matching_crashes} ÷ {highest_crash_count} × 100 = {score['frequency']:.0f}",
    severity_math=(f"({injury_crashes}×{INJURY_POINTS} + {fatal_crashes}×{FATAL_POINTS}) = {raw_severity} pts; "
                   f"{raw_severity} ÷ {highest_raw_severity} × 100 = {score['severity']:.0f}"),
)
st.caption(
    f"CrashScore = 30% × Frequency + 70% × Severity = "
    f"0.3 × {score['frequency']:.0f} + 0.7 × {score['severity']:.0f} = {score['priority']:.0f}. "
    "Injury crashes include fatal crashes."
)
if unknown_count:
    st.caption(
        f"{plural(unknown_count, 'crash', 'crashes')} here had no injury severity recorded. "
        "They count toward Frequency but add no Severity points."
    )

# ---------- 3. Historical evidence ----------
st.markdown("#### Historical evidence")
injury_pct = calculate_percentage(injury_crashes, matching_crashes)
fatal_pct = calculate_percentage(fatal_crashes, matching_crashes)
stat_tiles([
    ("Total crashes", matching_crashes, "All matching records"),
    ("Injury crashes", injury_crashes, "KABCO K, A, B or C"),
    ("Fatal crashes", fatal_crashes, "KABCO K"),
])
st.caption(
    f"{injury_pct:.0f}% of these crashes involved an injury and {fatal_pct:.0f}% were fatal."
)

# ---------- 4. Map ----------
st.markdown("#### Where the crashes happened")
map_df = matching_df[["Latitude", "Longitude", "severity_code"]].dropna(subset=["Latitude", "Longitude"]).copy()
missing_location = matching_crashes - len(map_df)
if len(map_df) == 0:
    st.info("None of these crash records include a map location.")
else:
    map_df["color"] = map_df["severity_code"].apply(severity_color)
    st.map(map_df, latitude="Latitude", longitude="Longitude", color="color", size=18, height=360)
    map_legend(include_unknown=unknown_count > 0)
    if missing_location:
        st.caption(f"Not shown on the map: {plural(missing_location, 'crash', 'crashes')} with no recorded location.")

# ---------- 5. Patterns ----------
st.markdown("#### When and how crashes happened")
tab_time, tab_day, tab_month, tab_type = st.tabs(["Time of day", "Day of week", "Month", "Collision type"])
with tab_time:
    hour_chart(matching_df)
with tab_day:
    weekday_chart(matching_df)
with tab_month:
    month_chart(matching_df, coverage["months"])
    st.caption("Only the months included in this limited sample are shown.")
with tab_type:
    crash_type_chart(matching_df)

# ---------- 6. Summary ----------
st.markdown("#### What the data shows")
points = [f"{plural(matching_crashes, 'crash', 'crashes')} matched this location in the data."]
points.append(f"{injury_crashes} involved an injury and {fatal_crashes} involved a death.")
hours = matching_df["Hour of the Day"].dropna()
if len(hours):
    busiest_hour = int(hours.value_counts().idxmax())
    hour_count = int(hours.value_counts().max())
    if hour_count > 1:
        nice = f"{busiest_hour % 12 or 12}{'am' if busiest_hour < 12 else 'pm'}"
        points.append(f"The most common hour was the {nice} hour ({plural(hour_count, 'crash', 'crashes')}).")
types = matching_df[TYPE_COLUMN].dropna()
if len(types):
    top_type = types.value_counts().idxmax()
    top_count = int(types.value_counts().max())
    points.append(f"The most common collision type was “{top_type}” ({plural(top_count, 'crash', 'crashes')}).")
st.markdown("\n".join(f"- {p}" for p in points))

with st.expander("See the crash records behind this result"):
    columns = [c for c in ["CrashId", "Month", "Day of the Week Text Format", "Hour of the Day",
                           "Roadway Name", "Intersecting Roadway Name", "Most Severe Injury", TYPE_COLUMN]
               if c in matching_df.columns]
    st.dataframe(matching_df[columns], hide_index=True, width="stretch")

st.page_link("views/navigator.py", label="Plan a safer route in Navigator", icon=":material/navigation:")
st.page_link("views/compare.py", label="Compare this location with another", icon=":material/compare_arrows:")

footer(f'Town of South Windsor, CT (limited sample)')
