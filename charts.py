"""
Chart helpers. Every chart uses the same colors, fonts and sizes so the
app reads as one product, and every chart counts real records only.
"""
import altair as alt
import pandas as pd
import streamlit as st

from shared import DAY_ORDER, MONTH_NAMES, TYPE_COLUMN
from ui import CHART_MAIN, INK, LINE, MUTED

FONT = "Source Sans Pro, sans-serif"


def _style(chart, title, subtitle=None):
    return (
        chart.properties(
            title=alt.TitleParams(title, subtitle=subtitle or "", anchor="start", fontSize=15,
                                  fontWeight=700, color=INK, subtitleColor=MUTED, subtitleFontSize=12, font=FONT,
                                  subtitleFont=FONT),
        )
        .configure_axis(labelColor=MUTED, titleColor=MUTED, gridColor=LINE, domainColor=LINE,
                        tickColor=LINE, labelFont=FONT, titleFont=FONT, labelFontSize=11, titleFontSize=11,
                        titleFontWeight=600)
        .configure_view(stroke=None)
    )


def _show(chart, alt_text, missing=0, missing_what="records"):
    st.altair_chart(chart, width="stretch", theme=None, alt=alt_text)
    if missing:
        st.caption(f"{missing} {missing_what} had no value for this field and are not shown.")


def vertical_counts(counts, x_title, title, subtitle, label_angle=0, label_expr=None):
    data = pd.DataFrame({"label": counts.index.astype(str), "Crashes": counts.values})
    axis = alt.Axis(labelAngle=label_angle, title=x_title, labelExpr=label_expr) if label_expr else \
        alt.Axis(labelAngle=label_angle, title=x_title)
    chart = alt.Chart(data, height=220).mark_bar(color=CHART_MAIN, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("label:N", sort=list(data["label"]), axis=axis),
        y=alt.Y("Crashes:Q", axis=alt.Axis(title="Crashes", tickMinStep=1, format="d")),
        tooltip=[alt.Tooltip("label:N", title=x_title or "Group"), alt.Tooltip("Crashes:Q")],
    )
    return _style(chart, title, subtitle)


def month_chart(df, months):
    """Crashes per month, for every month the data covers (months with no crashes show 0)."""
    month_values = pd.to_numeric(df["Month"], errors="coerce")
    counts = month_values.value_counts().reindex(months, fill_value=0)
    counts.index = [MONTH_NAMES[m - 1][:3] for m in months]
    chart = vertical_counts(counts, None, "Crashes by month", "Months covered by the data")
    _show(chart, "Bar chart of crashes by month.", int(month_values.isna().sum()))


def weekday_chart(df):
    days = df["Day of the Week Text Format"].astype("string").str.strip().str.title()
    counts = days.value_counts().reindex(DAY_ORDER, fill_value=0)
    counts.index = [d[:3] for d in DAY_ORDER]
    chart = vertical_counts(counts, None, "Crashes by day of the week", None)
    _show(chart, "Bar chart of crashes by day of the week.", int(days.isna().sum()))


def hour_chart(df):
    hours = pd.to_numeric(df["Hour of the Day"], errors="coerce")
    counts = hours.value_counts().reindex(range(24), fill_value=0)
    counts.index = [str(h) for h in range(24)]
    # Label every 3rd hour so the axis stays readable on a phone.
    label_expr = ("datum.value % 3 == 0 ? (datum.value == 0 ? '12am' : datum.value < 12 ? datum.value + 'am' : "
                  "datum.value == 12 ? '12pm' : (datum.value - 12) + 'pm') : ''")
    chart = vertical_counts(counts, "Hour of day", "Crashes by time of day", "Hour the crash happened",
                            label_expr=label_expr)
    _show(chart, "Bar chart of crashes by hour of day.", int(hours.isna().sum()))


def crash_type_chart(df):
    types = df[TYPE_COLUMN].astype("string").str.strip()
    counts = types.value_counts()
    data = counts.rename_axis("Crash type").reset_index(name="Crashes")
    chart = alt.Chart(data, height=max(120, 34 * len(data))).mark_bar(
        color=CHART_MAIN, cornerRadiusTopRight=3, cornerRadiusBottomRight=3
    ).encode(
        y=alt.Y("Crash type:N", sort="-x", axis=alt.Axis(title=None, labelLimit=180)),
        x=alt.X("Crashes:Q", axis=alt.Axis(title="Crashes", tickMinStep=1, format="d")),
        tooltip=["Crash type:N", "Crashes:Q"],
    )
    text = chart.mark_text(align="left", dx=4, color=INK, fontSize=11).encode(text="Crashes:Q")
    chart = _style(alt.layer(chart, text), "Types of collision", "Most common first")
    _show(chart, "Horizontal bar chart of crashes by type of collision.", int(types.isna().sum()))
