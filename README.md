# CrashLens
**Smarter Insights. Safer Roads.**

CrashLens helps teen drivers and their parents find safer routes, ones with fewer recorded crashes, using real
Connecticut police crash records, and opens the route in Google Maps to drive it. It was built with Python and
Streamlit for the 2026 Congressional App Challenge.

## What it does
- **Navigator** (the first page): enter a start and destination, pick the right address matches, and compare the
  driving routes by the crashes recorded along each. If the fastest route passes a road with a CrashScore above
  50 out of 100, Navigator suggests an alternate route (building its own detours if needed) and opens it in
  Google Maps.
- **CrashScore (experimental v0.1)**: a 0–100 score for each road combining how many crashes it has
  (Frequency, 30%) and how severe they were (Severity, 70%), with the full arithmetic shown.
- **Road Lookup**: pick a town and road (optionally a crossing road) to see its score, a map and charts,
  plus a ranking of every road in the data.
- **Compare**: two locations side by side, with a plain-English reason one ranks above the other.

CrashLens compares crash history only. It is **not** a prediction of future crashes, **not** an official safety
rating, and it does not account for traffic volume.

## Run it on your computer
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```
The app needs the crash data file at `data/ct_crashes_sample.csv`.

## Run the tests
```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
The tests use a tiny made-up file (`tests/fixtures/test_crashes.csv`) built to cover edge cases.
It is never shown in the app.

## Deploy
**Streamlit Community Cloud:** push this repository to GitHub, including `data/ct_crashes_sample.csv`
(`.gitignore` allows that one file). Then, at share.streamlit.io, choose **Create app**, select the repository,
branch `main`, and main file `app.py`.

## Project layout
| File | What it does |
|---|---|
| `app.py` | Starts the app: page setup, brand header, navigation |
| `priority_score.py` | The CrashScore formula (Frequency, Severity, weights) |
| `shared.py` | Loading and cleaning the data, matching searches, the comparison baseline |
| `routing.py` | Address lookup, driving routes, detours, Google Maps links, distance from crashes to a route |
| `ui.py` | Colors, styles and small display pieces (score card, header, footer) |
| `charts.py` | The bar charts |
| `views/` | One file per page (`navigator.py` is the first page) |
| `tests/` | Automated checks |
| `explore_data.py` | Early hand-checks of the score formula |
