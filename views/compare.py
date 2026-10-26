import streamlit as st

from shared import (
    explain_no_match,
    get_comparison_baseline,
    get_coverage,
    get_data,
    location_inputs,
    location_label,
    normalize_road_input,
    normalize_town,
    score_location,
)
from ui import html_block, bar, esc, footer

df = get_data()
coverage = get_coverage(df)
highest_crash_count, highest_raw_severity = get_comparison_baseline(df)

st.subheader("Compare two locations")
st.caption("See two roads or intersections side by side, for example two ways to school, and which parts of the "
           "CrashScore separate them.")

# Start Location A from the last search, if there was one.
last_search = st.session_state.get("search", {})

col_a, col_b = st.columns(2)
with col_a:
    with st.container(border=True):
        st.markdown("**Location A**")
        town_a, road_a, cross_a = location_inputs(df, "cmp_a", last_search)
with col_b:
    with st.container(border=True):
        st.markdown("**Location B**")
        town_b, road_b, cross_b = location_inputs(df, "cmp_b")

clicked = st.button("Compare", type="primary", width="stretch")

if clicked:
    if not (town_a.strip() and road_a.strip() and town_b.strip() and road_b.strip()):
        st.warning("Please choose a town and road for both locations.")
    else:
        st.session_state["compare"] = (town_a, road_a, cross_a, town_b, road_b, cross_b)

pair = st.session_state.get("compare")
if not pair:
    footer(f'Town of South Windsor, CT (limited sample)')
    st.stop()

town_a, road_a, cross_a, town_b, road_b, cross_b = pair


def same_location():
    def key(town, road, cross):
        roads = frozenset([normalize_road_input(road), normalize_road_input(cross)]) - {""}
        return normalize_town(town), roads
    return key(town_a, road_a, cross_a) == key(town_b, road_b, cross_b)


if same_location():
    st.info("Location A and Location B are the same place. Choose a different road or intersection for one of them.")
    st.stop()

result_a = score_location(df, town_a, road_a, cross_a, highest_crash_count, highest_raw_severity)
result_b = score_location(df, town_b, road_b, cross_b, highest_crash_count, highest_raw_severity)

missing = False
for name, result, town, road, cross in [("A", result_a, town_a, road_a, cross_a), ("B", result_b, town_b, road_b, cross_b)]:
    if len(result["matching_df"]) == 0:
        st.warning(f"**Location {name}:** " + explain_no_match(df, town, road, cross))
        missing = True
if missing:
    st.stop()

# Labels that can never collide (a collision used to hide one table column).
label_a = location_label(town_a, road_a, cross_a, df)
label_b = location_label(town_b, road_b, cross_b, df)
if normalize_town(town_a) != normalize_town(town_b):
    label_a += f" ({town_a.strip().title()})"
    label_b += f" ({town_b.strip().title()})"
if label_a == label_b:
    label_a, label_b = f"{label_a} (A)", f"{label_b} (B)"

st.divider()


def score_tile(column, letter, label, result):
    with column:
        html_block(f"""<div class="cl-part">
            <div class="cl-part-head"><span class="cl-eyebrow">Location {letter}</span><span class="cl-badge">Experimental v0.1</span></div>
            <div class="cl-part-name" style="margin-bottom:0.25rem">{esc(label)}</div>
            <div class="cl-part-value">{result['priority']:.0f}<span> / 100 CrashScore</span></div>{bar(result['priority'])}
            </div>""")


tile_a, tile_b = st.columns(2)
score_tile(tile_a, "A", label_a, result_a)
score_tile(tile_b, "B", label_b, result_b)

rows = [
    ("Crashes on record", str(len(result_a["matching_df"])), str(len(result_b["matching_df"]))),
    ("Injury crashes", str(len(result_a["injury_df"])), str(len(result_b["injury_df"]))),
    ("Fatal crashes", str(len(result_a["fatal_df"])), str(len(result_b["fatal_df"]))),
    ("Frequency (30%)", f"{result_a['frequency']:.0f} / 100", f"{result_b['frequency']:.0f} / 100"),
    ("Severity (70%)", f"{result_a['severity']:.0f} / 100", f"{result_b['severity']:.0f} / 100"),
    ("CrashScore", f"{result_a['priority']:.0f} / 100", f"{result_b['priority']:.0f} / 100"),
]
st.dataframe(
    {"Measure": [r[0] for r in rows], "A": [r[1] for r in rows], "B": [r[2] for r in rows]},
    hide_index=True,
    width="stretch",
    column_config={"A": st.column_config.TextColumn(f"A · {label_a}"), "B": st.column_config.TextColumn(f"B · {label_b}")},
)

st.markdown("#### Why did one rank above the other?")

if round(result_a["priority"]) == round(result_b["priority"]):
    st.write(f"**{label_a}** and **{label_b}** have the same CrashScore ({result_a['priority']:.0f}/100).")
else:
    if result_a["priority"] > result_b["priority"]:
        higher, lower, higher_result, lower_result = label_a, label_b, result_a, result_b
    else:
        higher, lower, higher_result, lower_result = label_b, label_a, result_b, result_a

    reasons = []
    if higher_result["frequency"] > lower_result["frequency"]:
        reasons.append("more crashes on record")
    if higher_result["severity"] > lower_result["severity"]:
        reasons.append("a more severe crash history (more injury and/or fatal crashes)")

    if reasons:
        st.write(f"**{higher}** ranks above **{lower}** because it has {' and '.join(reasons)}.")
    else:
        st.write(f"**{higher}** ranks above **{lower}** because of how Frequency (30%) and Severity (70%) combine.")

    if higher_result["severity"] > lower_result["severity"] and higher_result["frequency"] < lower_result["frequency"]:
        st.caption(f"{lower} has more crashes, but Severity counts for 70% of the score, so the more severe history ranks higher.")

if cross_a.strip() or cross_b.strip():
    st.caption("Intersections are scored against whole roads, so an intersection usually scores lower than a full road. "
               "Comparing intersection with intersection, or road with road, is the fairest comparison.")
st.caption("Based on historical crash records. This comparison does not predict future crashes.")

footer(f'Town of South Windsor, CT (limited sample)')
