from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Global Comparison | Global Culture Access Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.chart_utils import ordered_summary, render_global_dashboard
from utils.data_loader import load_all_data, validate_data
from utils.exchange_rate import clear_exchange_rate_cache, exchange_rates_to_dataframe, get_exchange_rates
from utils.map_utils import render_global_map
from utils.price_utils import format_price, format_usd

GLOBAL_VISITOR_TYPES = ["Adult", "Student", "Senior", "Child", "Disabled"]
DISPLAY_COLUMNS = [
    "facility_id",
    "city",
    "name",
    "category",
    "currency",
    "adult_price",
    "adult_price_usd",
    "student_price",
    "student_price_usd",
    "senior_price",
    "senior_price_usd",
    "child_price",
    "child_price_usd",
    "disabled_price",
    "disabled_price_usd",
    "wheelchair_access",
    "accessible_restroom",
    "elevator",
    "night_opening",
    "website",
]


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def _currency_by_city(facilities_df: pd.DataFrame) -> dict[str, str]:
    return facilities_df.groupby("city")["currency"].first().to_dict()


def _format_percent(value: object) -> str:
    if pd.isna(value):
        return "No data"
    return f"{float(value) * 100:.1f}%"


def _format_summary(summary_df: pd.DataFrame, facilities_df: pd.DataFrame) -> pd.DataFrame:
    currency_map = _currency_by_city(facilities_df)
    result = summary_df.copy()
    result["average_adult_price_local"] = result.apply(
        lambda row: format_price(row["average_adult_price_local"], currency_map.get(row["city"], "")), axis=1
    )
    result["average_selected_price_local"] = result.apply(
        lambda row: format_price(row["average_selected_price_local"], currency_map.get(row["city"], "")), axis=1
    )
    result["average_adult_price_usd"] = result["average_adult_price_usd"].apply(format_usd)
    result["average_selected_price_usd"] = result["average_selected_price_usd"].apply(format_usd)
    result["student_discount_ratio"] = result["student_discount_ratio"].apply(_format_percent)
    result["senior_discount_ratio"] = result["senior_discount_ratio"].apply(_format_percent)
    result["accessibility_ratio"] = result["accessibility_ratio"].apply(_format_percent)
    return result.rename(
        columns={
            "city": "City",
            "facility_count": "Facilities",
            "average_adult_price_local": "Average adult fee (local)",
            "average_adult_price_usd": "Average adult fee (USD)",
            "average_selected_price_local": "Average selected visitor fee (local)",
            "average_selected_price_usd": "Average selected visitor fee (USD)",
            "free_count": "Free for selected visitor",
            "student_discount_ratio": "Student discount ratio",
            "senior_discount_ratio": "Senior discount ratio",
            "accessibility_ratio": "Accessibility-feature ratio",
            "night_opening_count": "Night-opening facilities",
            "monday_closed_count": "Monday-closed facilities",
        }
    )


def _display_downloads(facilities_df: pd.DataFrame, opening_hours_df: pd.DataFrame) -> None:
    exchange_df = exchange_rates_to_dataframe(get_exchange_rates(use_live=True))
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            label="Download facilities with USD columns",
            data=facilities_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="facilities_with_usd.csv",
            mime="text/csv",
        )
    with col2:
        st.download_button(
            label="Download opening_hours.csv",
            data=opening_hours_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="opening_hours.csv",
            mime="text/csv",
        )
    with col3:
        st.download_button(
            label="Download exchange_rates.csv",
            data=exchange_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="exchange_rates.csv",
            mime="text/csv",
        )


st.title("Global Comparison Dashboard")
st.caption("서울 · 뉴욕 · 파리 문화시설 접근성 비교")

try:
    facilities_df, opening_hours_df = load_all_data(include_usd=True, use_live_rates=True)
except Exception as exc:
    st.error("데이터 파일을 불러오지 못했습니다. `data/facilities.csv`와 `data/opening_hours.csv` 위치를 확인하세요.")
    st.exception(exc)
    st.stop()

with st.sidebar:
    st.header("Dashboard options")
    visitor_type = st.selectbox(
        "Visitor type for price comparison",
        GLOBAL_VISITOR_TYPES,
        index=0,
        help="전 도시에서 공통적으로 비교 가능한 방문자 유형입니다.",
    )
    if st.button("Refresh KITA exchange rates with Selenium"):
        clear_exchange_rate_cache()
        _rerun()

fx = facilities_df.attrs.get("exchange_rate", {})
st.caption(
    f"USD conversion: KITA 매매기준율 via Selenium/cache. "
    f"USD/KRW={fx.get('usd_krw_rate')}, EUR/KRW={fx.get('eur_krw_rate')}, "
    f"status={fx.get('status')}, fetched_at={fx.get('fetched_at')}"
)

warnings = validate_data(facilities_df, opening_hours_df)
if warnings:
    with st.expander("Data quality warnings", expanded=True):
        for warning in warnings:
            st.warning(warning)

summary_df = ordered_summary(facilities_df, opening_hours_df, visitor_type=visitor_type)
formatted_summary = _format_summary(summary_df, facilities_df)

tab_overview, tab_charts, tab_fx, tab_map, tab_data = st.tabs(
    ["Overview", "Charts", "Exchange rates", "Global map", "Data table"]
)

with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cities", facilities_df["city"].nunique())
    col2.metric("Facilities", len(facilities_df))
    col3.metric("Weekly schedule rows", len(opening_hours_df))
    col4.metric("Selected visitor", visitor_type)

    st.markdown("### City-level summary")
    st.dataframe(formatted_summary, width = 'stretch', hide_index=True)

    st.info(
        "도시 간 입장료 비교는 USD 환산 컬럼을 기준으로 해석하세요. "
        "환산에는 KITA 환율종합 페이지의 실시간 매매기준율 중 USD/KRW와 EUR/KRW가 사용됩니다."
    )

with tab_charts:
    st.markdown("### Visual comparison")
    try:
        rendered_summary = render_global_dashboard(facilities_df, opening_hours_df, visitor_type=visitor_type)
    except ImportError as exc:
        st.error("차트를 표시하려면 `plotly`가 필요합니다. requirements.txt를 설치했는지 확인하세요.")
        st.exception(exc)
    else:
        with st.expander("Chart data"):
            st.dataframe(_format_summary(rendered_summary, facilities_df), width = 'stretch', hide_index=True)

with tab_fx:
    st.markdown("### KITA real-time exchange rates")
    exchange_result = get_exchange_rates(use_live=True)
    st.dataframe(exchange_rates_to_dataframe(exchange_result), width = 'stretch', hide_index=True)
    st.write(exchange_result.message)

with tab_map:
    st.markdown("### Seoul · New York · Paris facilities")
    st.write("마커를 클릭하면 시설명, 설명, 접근성 정보, 공식 웹사이트 링크를 볼 수 있습니다.")
    try:
        render_global_map(facilities_df, height=620)
    except Exception as exc:
        st.error("지도를 표시하지 못했습니다. `folium`과 `streamlit-folium` 설치 여부를 확인하세요.")
        st.exception(exc)

with tab_data:
    st.markdown("### Facility data")
    city_filter = st.multiselect(
        "Filter by city",
        options=facilities_df["city"].drop_duplicates().tolist(),
        default=facilities_df["city"].drop_duplicates().tolist(),
    )
    filtered_facilities = facilities_df[facilities_df["city"].isin(city_filter)].reset_index(drop=True)
    shown_columns = [column for column in DISPLAY_COLUMNS if column in filtered_facilities.columns]
    st.dataframe(filtered_facilities[shown_columns], width = 'stretch', hide_index=True)

    with st.expander("Opening-hours data"):
        opening_filter = opening_hours_df[
            opening_hours_df["facility_id"].isin(filtered_facilities["facility_id"])
        ].reset_index(drop=True)
        st.dataframe(opening_filter, width = 'stretch', hide_index=True)

    _display_downloads(filtered_facilities, opening_hours_df)
