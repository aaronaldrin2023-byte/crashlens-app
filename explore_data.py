import pandas as pd
from priority_score import (
    calculate_frequency_score,
    calculate_severity_score,
    calculate_raw_severity,
    calculate_priority_score,
    score_intersection,
)

df = pd.read_csv("data/ct_crashes_sample.csv")

matching_df = df[
    (df["Town Name"].str.strip().str.lower() == "south windsor".lower())
    &
    (df["Roadway Name"].str.strip().str.lower() == "buckland rd".lower())
]

print("Total rows:", len(df))
print("Unique crashes:", df["CrashId"].nunique())

# --- Step 2/5: manual formula check ---
# Frequency=60, Severity=80, weights 30/70 -> expected 74
test_score = calculate_priority_score(60, 80)
print("\nManual formula check (expect 74):", test_score)

# --- Step 9: zero case ---
print("\n--- Zero-case tests ---")
print("Zero crashes, normal comparison group:", calculate_frequency_score(0, 18))
print("Empty comparison group (highest=0):", calculate_frequency_score(5, 0))
print("Zero injury/fatal, normal comparison group:", calculate_severity_score(0, 0, 15))
print("Empty comparison group (highest=0):", calculate_severity_score(2, 1, 0))

# --- Real roads (South Windsor sample) ---
roads = {
    "Buckland Rd":        {"total": 18, "injury": 5, "fatal": 0},
    "Pleasant Valley Rd":  {"total": 5,  "injury": 2, "fatal": 0},
    "Rye St":              {"total": 4,  "injury": 1, "fatal": 0},
}

highest_crash_count = max(r["total"] for r in roads.values())
highest_raw_severity = max(calculate_raw_severity(r["injury"], r["fatal"]) for r in roads.values())

print("\n--- Real road scores ---")
for name, r in roads.items():
    result = score_intersection(r["total"], r["injury"], r["fatal"], highest_crash_count, highest_raw_severity)
    print(f"{name}: {result}")

# --- Step 12: range check ---
# Frequency/Severity are each (this location's value / group MAX) * 100.
# Since the group max always includes this location's own value, the
# location's value can never exceed the max -> each component is
# mathematically bounded to [0, 100]. Priority is a weighted average
# of two values in [0, 100] with weights summing to 1.0, so it's also
# bounded to [0, 100]. No clamping needed -- verified by construction,
# not just tested.
print("\n--- Step 12: range check ---")
print("Highest possible input (location IS the max) -> Frequency:",
      calculate_frequency_score(18, 18), "Severity:", calculate_severity_score(5, 0, 15))

# --- Step 18: manual verification of one real intersection, start to finish ---
# Buckland Rd: 18 crashes, 5 injury, 0 fatal.
# Frequency = 18 / 18 * 100 = 100
# Raw severity = (5*3) + (0*10) = 15; highest raw severity = 15 (Buckland is the max)
# Severity = 15 / 15 * 100 = 100
# Priority = (100 * 0.30) + (100 * 0.70) = 100
print("\n--- Step 18: manual verification (Buckland Rd) ---")
print("Expected: Frequency=100, Severity=100, Priority=100")
print("Python:  ", score_intersection(18, 5, 0, highest_crash_count, highest_raw_severity))

# --- Day 2: stress-test scenarios ---
stress_tests = {
    "High freq, low severity":        {"total": 50, "injury": 2, "fatal": 0},
    "Low freq, high severity":        {"total": 3,  "injury": 2, "fatal": 1},
    "Moderate freq, high injury share": {"total": 10, "injury": 8, "fatal": 0},
    "Zero crashes":                   {"total": 0,  "injury": 0, "fatal": 0},
    "One fatal, very few crashes":    {"total": 2,  "injury": 0, "fatal": 1},
    "Very high count, no severity":   {"total": 100, "injury": 0, "fatal": 0},
}

stress_highest_count = max(t["total"] for t in stress_tests.values())
stress_highest_severity = max(calculate_raw_severity(t["injury"], t["fatal"]) for t in stress_tests.values())

print("\n--- Day 2: stress tests ---")
for name, t in stress_tests.items():
    result = score_intersection(t["total"], t["injury"], t["fatal"], stress_highest_count, stress_highest_severity)
    print(f"{name}: Frequency={result['frequency']:.1f}, Severity={result['severity']:.1f}, Priority={result['priority']:.1f}")
