import streamlit as st

from shared import explain_no_match, find_matching_crashes, get_coverage, get_data, location_inputs, rank_roads
from ui import html_block, esc, footer

df = get_data()
coverage = get_coverage(df)

html_block(f"""<div class="cl-hero">
    <h1>See the crash history behind every route.</h1>
    <p>Look up any road a teen driver uses to see what Navigator sees: how many crashes happened there,
    how serious they were, and the road's CrashScore.</p>
    <ol class="cl-steps">
      <li><b>1</b><div>Pick a town and road<span>Add a crossing road to focus on one intersection.</span></div></li>
      <li><b>2</b><div>Press Analyze<span>CrashLens matches every crash record for that location.</span></div></li>
      <li><b>3</b><div>Read the results<span>A CrashScore, the evidence behind it, a map and charts.</span></div></li>
    </ol></div>""")

st.markdown(
    f'<span class="cl-chip">Coverage: {esc(coverage["towns_text"])}</span>'
    f'<span class="cl-chip">Limited sample</span>'
    f'<span class="cl-chip">{coverage["crashes"]:,} crash records</span>',
    unsafe_allow_html=True,
)

# Remember the last search so coming back to this page doesn't blank the form.
saved = st.session_state.get("search", {})

with st.container(border=True):
    town, road, road_b = location_inputs(df, "home", saved)
    clicked = st.button("Analyze", type="primary", width="stretch")

if coverage["crashes"] > 0:
    share = coverage["with_cross_road"] / coverage["crashes"]
    st.caption(
        f"Tip: only about {share:.0%} of crash records list an intersecting road. "
        "If an intersection finds nothing, search the first road on its own."
    )

if clicked:
    if town.strip() == "" or road.strip() == "":
        st.warning("Please choose a town and a road first.")
    elif len(find_matching_crashes(df, town, road, road_b)) == 0:
        st.warning(explain_no_match(df, town, road, road_b))
    else:
        st.session_state["search"] = {"town": town, "road": road, "road_b": road_b}
        st.switch_page("views/search_results.py")

# ---------- Top locations ----------
ranking = rank_roads(df)
if not ranking.empty:
    st.markdown(f"#### Which {esc(coverage['towns_text'].replace(', CT', ''))} roads have the heaviest crash history?")
    st.caption(
        "Every road in the data, ranked by CrashScore. Roads near the top have the heaviest crash history "
        "(more crashes, more injuries), so Navigator steers around them when it can. Tap a row to see the full analysis."
    )
    show_all = st.toggle(f"Show all {len(ranking)} roads", key="rank_show_all")
    shown = ranking if show_all else ranking.head(10)
    table = shown[["rank", "label", "priority", "crashes", "injury", "fatal"]]
    picked = st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key="rank_table",
        column_config={
            "rank": st.column_config.NumberColumn("#", width="small"),
            "label": st.column_config.TextColumn("Road"),
            "priority": st.column_config.ProgressColumn("CrashScore", min_value=0, max_value=100, format="%.0f"),
            "crashes": st.column_config.NumberColumn("Crashes", width="small"),
            "injury": st.column_config.NumberColumn("Injury", width="small"),
            "fatal": st.column_config.NumberColumn("Fatal", width="small"),
        },
    )
    selected_rows = picked.selection.rows if picked else []
    if selected_rows:
        choice = shown.iloc[selected_rows[0]]
        st.session_state["search"] = {"town": choice["town"], "road": choice["road"], "road_b": ""}
        st.switch_page("views/search_results.py")
    st.caption("Whole roads only. State routes are listed by direction (for example, US Route 5 southbound) "
               "because that is how crashes are recorded.")

st.page_link("views/navigator.py", label="Plan a safer route in Navigator", icon=":material/navigation:")

footer(f'Town of South Windsor, CT (limited sample)')
