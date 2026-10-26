import streamlit as st

from ui import apply_theme, brand_header

st.set_page_config(
    page_title="CrashLens · Safer routes for teen drivers",
    page_icon="🔎",
    layout="centered",
)

apply_theme()
brand_header()

# Navigator is the first page: CrashLens's main goal is helping teen drivers and their
# families pick routes with fewer recorded crashes.
navigator = st.Page("views/navigator.py", title="Navigator", icon=":material/navigation:", default=True)
home = st.Page("views/home.py", title="Road Lookup", icon=":material/search:", url_path="roads")
search_results = st.Page("views/search_results.py", title="Results", icon=":material/insights:")
compare = st.Page("views/compare.py", title="Compare", icon=":material/compare_arrows:")

page = st.navigation([navigator, home, search_results, compare], position="top")
page.run()
