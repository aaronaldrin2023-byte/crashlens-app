"""
Look and feel for CrashLens: brand colors, one stylesheet, and a few small
HTML building blocks (header, score card, footer).

The CSS mostly styles our own `cl-` classes, so a Streamlit update is
unlikely to break it. The few Streamlit selectors used are `data-testid`
attributes, which Streamlit keeps stable for testing.
"""
import html

import streamlit as st

BRAND = "#D24A46"
BRAND_DARK = "#A8322F"
INK = "#1F2430"
MUTED = "#5B6170"
LINE = "#E6E2DD"
SURFACE = "#FFFFFF"
CANVAS = "#FAF8F5"

# Chart colors (shared by every chart so they look like one system)
CHART_MAIN = BRAND
CHART_SOFT = "#E8A5A2"

CSS = f"""
<style>
:root {{
  --cl-brand: {BRAND};
  --cl-brand-dark: {BRAND_DARK};
  --cl-ink: {INK};
  --cl-muted: {MUTED};
  --cl-line: {LINE};
  --cl-surface: {SURFACE};
}}

/* Page width and breathing room */
[data-testid="stMainBlockContainer"] {{
  max-width: 820px;
  padding-top: 4.25rem;
  padding-bottom: 3rem;
}}

h1, h2, h3 {{ letter-spacing: -0.015em; color: var(--cl-ink); }}

/* ---------- Brand header ---------- */
.cl-header {{
  display: flex; align-items: center; gap: 0.75rem;
  padding-bottom: 1rem; margin-bottom: 0.5rem;
  border-bottom: 1px solid var(--cl-line);
}}
.cl-mark {{ flex: 0 0 auto; width: 40px; height: 40px; }}
.cl-wordmark {{ font-size: 1.6rem; font-weight: 750; color: var(--cl-ink); line-height: 1.1; }}
.cl-wordmark span {{ color: var(--cl-brand); }}
.cl-tagline {{ font-size: 0.9rem; color: var(--cl-muted); margin-top: 2px; }}

/* ---------- Home hero ---------- */
.cl-hero h1 {{
  font-size: clamp(1.75rem, 5.5vw, 2.6rem); line-height: 1.15;
  margin: 0.75rem 0 0.5rem 0; padding: 0;
}}
.cl-hero p {{ font-size: 1.05rem; color: var(--cl-muted); margin: 0 0 1.25rem 0; max-width: 40em; }}
.cl-steps {{
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem;
  margin: 0 0 1.5rem 0 !important; padding: 0 !important; list-style: none;
}}
.cl-steps li {{ margin: 0 !important;
  background: var(--cl-surface); border: 1px solid var(--cl-line); border-radius: 12px;
  padding: 0.85rem 0.9rem; font-size: 0.92rem; color: var(--cl-ink);
}}
.cl-steps b {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.5rem; height: 1.5rem; border-radius: 50%;
  background: var(--cl-brand); color: #fff; font-size: 0.8rem; margin-bottom: 0.4rem;
}}
.cl-steps span {{ display: block; color: var(--cl-muted); font-size: 0.85rem; margin-top: 2px; }}

/* ---------- Small labels ---------- */
.cl-eyebrow {{
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--cl-muted);
}}
.cl-badge {{
  display: inline-block; font-size: 0.72rem; font-weight: 600;
  padding: 0.15rem 0.55rem; border-radius: 999px;
  border: 1px solid var(--cl-brand); color: var(--cl-brand-dark); background: #FDF1F0;
}}
.cl-chip {{
  display: inline-block; font-size: 0.8rem; color: var(--cl-muted);
  background: #F1EEEA; border-radius: 999px; padding: 0.2rem 0.65rem; margin: 0 0.35rem 0.35rem 0;
}}
.cl-location h2 {{ font-size: clamp(1.5rem, 5vw, 2.1rem); margin: 0.25rem 0 0.1rem 0; padding: 0; }}
.cl-location p {{ color: var(--cl-muted); margin: 0 0 0.6rem 0; }}

/* ---------- CrashScore card ---------- */
.cl-score {{
  background: var(--cl-surface); border: 1px solid var(--cl-line);
  border-top: 4px solid var(--cl-brand); border-radius: 14px;
  padding: 1.25rem 1.35rem 1.1rem 1.35rem; margin: 0.5rem 0 1rem 0;
  box-shadow: 0 1px 2px rgba(31, 36, 48, 0.04), 0 4px 16px rgba(31, 36, 48, 0.05);
}}
.cl-score-top {{ display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}
.cl-score-value {{
  font-size: clamp(3rem, 14vw, 4.5rem); font-weight: 800; line-height: 1;
  color: var(--cl-ink); margin: 0.6rem 0 0.75rem 0; font-variant-numeric: tabular-nums;
}}
.cl-score-value span {{ font-size: 0.35em; font-weight: 600; color: var(--cl-muted); margin-left: 0.15em; }}
.cl-bar {{ height: 10px; background: #F1EEEA; border-radius: 999px; overflow: hidden; }}
.cl-bar > div {{ height: 100%; background: var(--cl-brand); border-radius: 999px; }}
.cl-score p {{ margin: 0.85rem 0 0 0; color: var(--cl-ink); font-size: 0.98rem; }}
.cl-score .cl-fine {{ color: var(--cl-muted); font-size: 0.85rem; margin-top: 0.5rem; }}

/* ---------- Score components ---------- */
.cl-parts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.5rem; }}
.cl-part {{
  background: var(--cl-surface); border: 1px solid var(--cl-line); border-radius: 12px; padding: 0.9rem 1rem;
}}
.cl-part-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.45rem; }}
.cl-part-name {{ font-weight: 700; color: var(--cl-ink); }}
.cl-part-weight {{ font-size: 0.78rem; color: var(--cl-muted); }}
.cl-part-value {{ font-size: 1.6rem; font-weight: 750; color: var(--cl-ink); font-variant-numeric: tabular-nums; }}
.cl-part-value span {{ font-size: 0.85rem; color: var(--cl-muted); font-weight: 600; }}
.cl-part .cl-bar {{ height: 7px; margin: 0.35rem 0 0.6rem 0; }}
.cl-part p {{ margin: 0; font-size: 0.85rem; color: var(--cl-muted); }}
.cl-math {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.78rem; color: var(--cl-muted); margin-top: 0.35rem !important; }}

/* ---------- Metric cards (Streamlit's own st.metric) ---------- */
[data-testid="stMetric"] {{
  background: var(--cl-surface); border: 1px solid var(--cl-line); border-radius: 12px;
  padding: 0.75rem 0.95rem;
}}
[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}

/* ---------- Stat tiles: stay three-across even on phones ---------- */
.cl-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.6rem; margin-bottom: 0.4rem; }}
.cl-stat {{ background: var(--cl-surface); border: 1px solid var(--cl-line); border-radius: 12px; padding: 0.75rem 0.85rem; }}
.cl-stat-label {{ font-size: 0.8rem; color: var(--cl-muted); font-weight: 600; }}
.cl-stat-value {{ font-size: clamp(1.4rem, 6vw, 2rem); font-weight: 750; color: var(--cl-ink); font-variant-numeric: tabular-nums; line-height: 1.2; }}
.cl-stat-note {{ font-size: 0.72rem; color: var(--cl-muted); }}

/* ---------- Legend for maps ---------- */
.cl-legend {{ display: flex; flex-wrap: wrap; gap: 0.35rem 1rem; font-size: 0.85rem; color: var(--cl-muted); margin: 0.25rem 0 0.5rem 0; }}
.cl-legend i {{ display: inline-block; width: 0.75rem; height: 0.75rem; border-radius: 50%; margin-right: 0.35rem; vertical-align: -1px; border: 1px solid #fff; box-shadow: 0 0 0 1px rgba(0,0,0,0.15); }}

/* ---------- Footer ---------- */
.cl-footer {{
  margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--cl-line);
  font-size: 0.82rem; color: var(--cl-muted); line-height: 1.5;
}}
.cl-footer b {{ color: var(--cl-ink); }}

/* ---------- Buttons: comfortable touch targets ---------- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {{
  min-height: 2.9rem; font-weight: 600; border-radius: 10px;
}}

/* ---------- Phones (about 375–430 px wide) ---------- */
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ padding-left: 1rem; padding-right: 1rem; padding-top: 3.5rem; }}
  .cl-steps {{ grid-template-columns: 1fr; gap: 0.5rem; }}
  .cl-steps li {{ display: flex; gap: 0.75rem; align-items: flex-start; padding: 0.7rem 0.8rem; }}
  .cl-steps b {{ flex: 0 0 auto; margin-bottom: 0; }}
  .cl-parts {{ grid-template-columns: 1fr; }}
  .cl-score {{ padding: 1rem 1rem 0.95rem 1rem; }}
  .cl-wordmark {{ font-size: 1.35rem; }}
  .cl-mark {{ width: 34px; height: 34px; }}
}}
</style>
"""

LENS_MARK = f"""
<svg class="cl-mark" viewBox="0 0 40 40" aria-hidden="true">
  <rect width="40" height="40" rx="10" fill="{BRAND}"/>
  <circle cx="18" cy="18" r="9" fill="none" stroke="#fff" stroke-width="3"/>
  <line x1="24.5" y1="24.5" x2="31" y2="31" stroke="#fff" stroke-width="3.4" stroke-linecap="round"/>
  <path d="M14 21 L17 17 L19.5 19.5 L23 14.5" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def esc(text):
    return html.escape(str(text))


def html_block(markup):
    """Shows our own HTML. Lines are joined first: Markdown treats indented lines as a code block."""
    st.markdown(" ".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def brand_header():
    html_block(f"""<div class="cl-header">{LENS_MARK}
        <div><div class="cl-wordmark">Crash<span>Lens</span></div>
        <div class="cl-tagline">Smarter Insights. Safer Roads.</div></div></div>""")


def footer(coverage_text=None):
    coverage = f" Data: {esc(coverage_text)}." if coverage_text else ""
    html_block(f"""<div class="cl-footer"><b>CrashLens</b> · Smarter Insights. Safer Roads.<br>
        A student-built app that helps teen drivers and their parents find safer routes, ones with fewer recorded
        crashes, for the 2026 Congressional App Challenge.{coverage}
        Based on historical crash records. Not an official government safety rating and not a prediction of future crashes.</div>""")


def location_heading(title, subtitle):
    st.markdown(
        f'<div class="cl-location"><h2>{esc(title)}</h2><p>{esc(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def bar(value):
    width = max(0.0, min(100.0, float(value)))
    return f'<div class="cl-bar" role="img" aria-label="{width:.0f} out of 100"><div style="width:{width:.1f}%"></div></div>'


def score_card(priority, explanation_html, fine_print):
    html_block(f"""<div class="cl-score">
        <div class="cl-score-top"><span class="cl-eyebrow">CrashScore</span><span class="cl-badge">Experimental model v0.1</span></div>
        <div class="cl-score-value">{priority:.0f}<span>/ 100</span></div>
        {bar(priority)}
        <p>{explanation_html}</p>
        <p class="cl-fine">{esc(fine_print)}</p>
        </div>""")


def score_parts(frequency, severity, frequency_note, severity_note, frequency_math, severity_math):
    html_block(f"""<div class="cl-parts">
        <div class="cl-part">
          <div class="cl-part-head"><span class="cl-part-name">Frequency</span><span class="cl-part-weight">30% of score</span></div>
          <div class="cl-part-value">{frequency:.0f}<span> / 100</span></div>{bar(frequency)}
          <p>{esc(frequency_note)}</p><p class="cl-math">{esc(frequency_math)}</p>
        </div>
        <div class="cl-part">
          <div class="cl-part-head"><span class="cl-part-name">Severity</span><span class="cl-part-weight">70% of score</span></div>
          <div class="cl-part-value">{severity:.0f}<span> / 100</span></div>{bar(severity)}
          <p>{esc(severity_note)}</p><p class="cl-math">{esc(severity_math)}</p>
        </div></div>""")


def stat_tiles(items):
    """items: list of (label, value, note)."""
    tiles = "".join(
        f'<div class="cl-stat"><div class="cl-stat-label">{esc(label)}</div>'
        f'<div class="cl-stat-value">{esc(value)}</div><div class="cl-stat-note">{esc(note)}</div></div>'
        for label, value, note in items
    )
    html_block(f'<div class="cl-stats">{tiles}</div>')


def map_legend(include_endpoints=False, include_unknown=False):
    def dot(rgb):
        return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"

    from shared import SEVERITY_COLORS

    items = []
    if include_endpoints:
        items += [(ENDPOINT_COLORS["start"], "Start (A)"), (ENDPOINT_COLORS["end"], "Destination (B)")]
    items += [
        (SEVERITY_COLORS["fatal"], "Fatal crash"),
        (SEVERITY_COLORS["injury"], "Injury crash"),
        (SEVERITY_COLORS["none"], "No apparent injury"),
    ]
    if include_unknown:
        items.append((SEVERITY_COLORS["unknown"], "Severity not recorded"))
    spans = "".join(f'<span><i style="background:{dot(c)}"></i>{esc(t)}</span>' for c, t in items)
    st.markdown(f'<div class="cl-legend">{spans}</div>', unsafe_allow_html=True)


ENDPOINT_COLORS = {"start": [46, 160, 67], "end": [111, 66, 193]}
