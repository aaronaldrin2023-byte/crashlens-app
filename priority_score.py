"""
CrashLens CrashScore -- Experimental v0.1
(Called the "Priority Score" and "Danger Score" in earlier versions; the formula is unchanged.)

Components:
  Frequency: crash count normalized against the highest crash count
             in the comparison group (0-100).
  Severity:  (injury_crashes * 3) + (fatal_crashes * 10), normalized
             against the highest raw severity score in the comparison
             group (0-100). No-injury crashes contribute 0 points.
  Weights:   30% Frequency, 70% Severity.

This score is NOT a prediction of future crashes. It reflects relative
priority for further investigation, based only on the historical crash
records included in the comparison group.
"""

FREQUENCY_WEIGHT = 0.30
SEVERITY_WEIGHT = 0.70

INJURY_POINTS = 3
FATAL_POINTS = 10


def calculate_frequency_score(crash_count, highest_crash_count):
    if highest_crash_count == 0:
        return 0
    return (crash_count / highest_crash_count) * 100


def calculate_raw_severity(injury_crashes, fatal_crashes):
    return (injury_crashes * INJURY_POINTS) + (fatal_crashes * FATAL_POINTS)


def calculate_severity_score(injury_crashes, fatal_crashes, highest_raw_severity):
    if highest_raw_severity == 0:
        return 0
    raw_severity = calculate_raw_severity(injury_crashes, fatal_crashes)
    return (raw_severity / highest_raw_severity) * 100


def calculate_priority_score(frequency_component, severity_component):
    return (frequency_component * FREQUENCY_WEIGHT) + (severity_component * SEVERITY_WEIGHT)


def score_intersection(crash_count, injury_crashes, fatal_crashes, highest_crash_count, highest_raw_severity):
    """
    Scores one intersection against a comparison group.
    Returns a breakdown dict, not just the final number, so the app
    can explain where the score came from.
    """
    frequency = calculate_frequency_score(crash_count, highest_crash_count)
    severity = calculate_severity_score(injury_crashes, fatal_crashes, highest_raw_severity)
    priority = calculate_priority_score(frequency, severity)
    return {
        "crash_count": crash_count,
        "injury_crashes": injury_crashes,
        "fatal_crashes": fatal_crashes,
        "frequency": frequency,
        "severity": severity,
        "priority": priority,
    }
