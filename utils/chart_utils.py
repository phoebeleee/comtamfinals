#도시별 비교 대시보드 (Plotly, 생성형AI 도움 받아 작성)

from __future__ import annotations

import pandas as pd

from utils.filters import build_city_summary
from utils.price_utils import add_effective_price_column

try:
    import plotly.express as px
except Exception as exc:  # pragma: no cover
    px = None
    PLOTLY_IMPORT_ERROR = exc
else:
    PLOTLY_IMPORT_ERROR = None

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

CITY_ORDER = ["Seoul", "New York", "Paris"]


def _require_plotly() -> None:
    if px is None:
        raise ImportError("plotly is required for chart rendering") from PLOTLY_IMPORT_ERROR


def ordered_summary(
    facilities_df: pd.DataFrame,
    opening_hours_df: pd.DataFrame | None = None,
    visitor_type: str = "Adult",
) -> pd.DataFrame:
    """Build and order city-level summary metrics."""
    summary = build_city_summary(facilities_df, opening_hours_df, visitor_type=visitor_type)
    if summary.empty:
        return summary
    summary["city"] = pd.Categorical(summary["city"], categories=CITY_ORDER, ordered=True)
    return summary.sort_values("city").reset_index(drop=True)


def make_average_usd_price_chart(summary_df: pd.DataFrame):
    """Chart average USD-converted admission price by city."""
    _require_plotly()
    chart_df = summary_df.copy()
    chart_df["average_selected_price_usd"] = chart_df["average_selected_price_usd"].round(2)
    return px.bar(
        chart_df,
        x="city",
        y="average_selected_price_usd",
        text="average_selected_price_usd",
        title="Average Admission Fee by City (USD-converted)",
        labels={"city": "City", "average_selected_price_usd": "Average fee (USD)"},
    )


def make_average_local_price_chart(summary_df: pd.DataFrame):
    """Chart average local-currency admission price by city.

    This is shown only as a contextual chart because currencies differ.
    """
    _require_plotly()
    chart_df = summary_df.copy()
    return px.bar(
        chart_df,
        x="city",
        y="average_selected_price_local",
        text="average_selected_price_local",
        title="Average Admission Fee by City (Local Currency, Context Only)",
        labels={"city": "City", "average_selected_price_local": "Average local fee"},
    )


def make_free_facilities_chart(summary_df: pd.DataFrame):
    """Chart free-entry facility counts by city."""
    _require_plotly()
    return px.bar(
        summary_df,
        x="city",
        y="free_count",
        text="free_count",
        title="Free-Entry Facilities by City",
        labels={"city": "City", "free_count": "Number of free facilities"},
    )


def make_accessibility_chart(summary_df: pd.DataFrame):
    """Chart accessibility-feature ratio by city."""
    _require_plotly()
    chart_df = summary_df.copy()
    chart_df["accessibility_percent"] = (chart_df["accessibility_ratio"] * 100).round(1)
    return px.bar(
        chart_df,
        x="city",
        y="accessibility_percent",
        text="accessibility_percent",
        title="Facilities with Accessibility Features",
        labels={"city": "City", "accessibility_percent": "Share (%)"},
    )


def make_discount_ratio_chart(summary_df: pd.DataFrame):
    """Chart student and senior discount ratios by city."""
    _require_plotly()
    chart_df = summary_df.melt(
        id_vars="city",
        value_vars=["student_discount_ratio", "senior_discount_ratio"],
        var_name="visitor_type",
        value_name="discount_ratio",
    )
    chart_df["visitor_type"] = chart_df["visitor_type"].map(
        {"student_discount_ratio": "Student", "senior_discount_ratio": "Senior"}
    )
    chart_df["discount_percent"] = (chart_df["discount_ratio"] * 100).round(1)
    return px.bar(
        chart_df,
        x="city",
        y="discount_percent",
        color="visitor_type",
        barmode="group",
        title="Discount Availability by Visitor Type",
        labels={"city": "City", "discount_percent": "Share (%)", "visitor_type": "Visitor type"},
    )


def make_night_opening_chart(summary_df: pd.DataFrame):
    """Chart night-opening facility counts by city."""
    _require_plotly()
    return px.bar(
        summary_df,
        x="city",
        y="night_opening_count",
        text="night_opening_count",
        title="Night-Opening Facilities by City",
        labels={"city": "City", "night_opening_count": "Night-opening facilities"},
    )


def make_monday_closed_chart(summary_df: pd.DataFrame):
    """Chart Monday-closed facility counts by city."""
    _require_plotly()
    return px.bar(
        summary_df,
        x="city",
        y="monday_closed_count",
        text="monday_closed_count",
        title="Monday-Closed Facilities by City",
        labels={"city": "City", "monday_closed_count": "Monday-closed facilities"},
    )


def make_visitor_usd_price_chart(
    facilities_df: pd.DataFrame,
    visitor_types: list[str] | None = None,
):
    """Grouped chart for average USD-converted price by city and visitor type."""
    _require_plotly()
    visitor_types = visitor_types or ["Adult", "Student", "Senior", "Child", "Disabled"]

    rows: list[dict[str, object]] = []
    for visitor_type in visitor_types:
        priced_df = add_effective_price_column(
            facilities_df, visitor_type, column_name="effective_price_usd", usd=True
        )
        grouped = priced_df.groupby("city")["effective_price_usd"].mean().reset_index()
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "city": row["city"],
                    "visitor_type": visitor_type,
                    "average_price_usd": round(float(row["effective_price_usd"]), 2),
                }
            )

    chart_df = pd.DataFrame(rows)
    chart_df["city"] = pd.Categorical(chart_df["city"], categories=CITY_ORDER, ordered=True)
    chart_df = chart_df.sort_values(["city", "visitor_type"])

    return px.bar(
        chart_df,
        x="city",
        y="average_price_usd",
        color="visitor_type",
        barmode="group",
        title="Average Admission Fee by Visitor Type (USD-converted)",
        labels={"city": "City", "average_price_usd": "Average fee (USD)", "visitor_type": "Visitor type"},
    )


def render_global_dashboard(
    facilities_df: pd.DataFrame,
    opening_hours_df: pd.DataFrame,
    visitor_type: str = "Adult",
) -> pd.DataFrame:
    """Render a ready-to-use Streamlit comparison dashboard.

    Returns the summary dataframe so the page can also display it as a table.
    """
    if st is None:
        raise ImportError("streamlit is required to render the dashboard")

    summary = ordered_summary(facilities_df, opening_hours_df, visitor_type=visitor_type)

    col1, col2, col3 = st.columns(3)
    col1.metric("Cities", summary["city"].nunique())
    col2.metric("Facilities", int(summary["facility_count"].sum()))
    col3.metric("Free facilities", int(summary["free_count"].sum()))

    st.plotly_chart(make_average_usd_price_chart(summary), use_container_width=True)
    st.plotly_chart(make_visitor_usd_price_chart(facilities_df), use_container_width=True)
    st.plotly_chart(make_free_facilities_chart(summary), use_container_width=True)
    st.plotly_chart(make_discount_ratio_chart(summary), use_container_width=True)
    st.plotly_chart(make_accessibility_chart(summary), use_container_width=True)
    st.plotly_chart(make_night_opening_chart(summary), use_container_width=True)
    st.plotly_chart(make_monday_closed_chart(summary), use_container_width=True)

    with st.expander("Local-currency context chart"):
        st.caption("Local-currency values are shown for context only; USD-converted charts should be used for cross-city fee comparison.")
        st.plotly_chart(make_average_local_price_chart(summary), use_container_width=True)

    return summary
