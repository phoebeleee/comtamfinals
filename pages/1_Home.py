from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Home | Global Culture Access Explorer",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.data_loader import load_all_data, load_raw_scraped_sources, validate_data
from utils.exchange_rate import clear_exchange_rate_cache, exchange_rates_to_dataframe, get_exchange_rates

CITY_PAGE_PATHS = {
    "Seoul": "pages/2_Seoul_Explorer.py",
    "New York": "pages/3_NewYork_Explorer.py",
    "Paris": "pages/4_Paris_Explorer.py",
    "Global Comparison": "pages/5_Global_Comparison.py",
}


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def _show_page_links() -> None:
    st.markdown("### Navigate")
    st.write("왼쪽 사이드바의 Pages 메뉴에서 페이지를 이동할 수 있습니다.")
    if hasattr(st, "page_link"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.page_link(CITY_PAGE_PATHS["Seoul"], label="Seoul Explorer", icon="🇰🇷")
        with col2:
            st.page_link(CITY_PAGE_PATHS["New York"], label="New York Explorer", icon="🇺🇸")
        with col3:
            st.page_link(CITY_PAGE_PATHS["Paris"], label="Paris Explorer", icon="🇫🇷")
        with col4:
            st.page_link(CITY_PAGE_PATHS["Global Comparison"], label="Global Comparison", icon="📊")


def _city_count_table(facilities_df: pd.DataFrame) -> pd.DataFrame:
    result = (
        facilities_df.groupby(["city", "currency"])
        .agg(
            facilities=("facility_id", "count"),
            categories=("category", "nunique"),
            free_adult_facilities=("adult_price", lambda s: int((pd.to_numeric(s, errors="coerce") == 0).sum())),
            avg_adult_usd=("adult_price_usd", "mean"),
        )
        .reset_index()
    )
    result["avg_adult_usd"] = result["avg_adult_usd"].round(2)
    return result.rename(
        columns={
            "city": "City",
            "currency": "Currency",
            "facilities": "Facilities",
            "categories": "Categories",
            "free_adult_facilities": "Free adult-entry facilities",
            "avg_adult_usd": "Average adult fee (USD)",
        }
    )


st.title("Global Culture Access Explorer")
st.caption("서울 · 뉴욕 · 파리 문화시설 접근성 분석 플랫폼")

try:
    facilities_df, opening_hours_df = load_all_data(include_usd=True, use_live_rates=True)
except Exception as exc:
    st.error("데이터 파일을 불러오지 못했습니다. `data/facilities.csv`와 `data/opening_hours.csv` 위치를 확인하세요.")
    st.exception(exc)
    st.stop()

fx = facilities_df.attrs.get("exchange_rate", {})

st.markdown(
    """
    이 웹앱은 서울, 뉴욕, 파리의 대표 문화시설 30곳을 대상으로 방문자가 실제로 궁금해하는
    세 가지 질문에 답하도록 설계되었습니다.

    1. 선택한 요일과 시간에 문화시설이 열려 있는가?
    2. 나의 방문자 유형에 적용되는 최저 입장료는 얼마인가?
    3. KITA 실시간 환율의 **매매기준율**로 환산한 USD 가격과 장애인 접근성 정보는 어떤가?
    """
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Cities", facilities_df["city"].nunique())
col2.metric("Facilities", len(facilities_df))
col3.metric("Opening-hour rows", len(opening_hours_df))
col4.metric("FX status", fx.get("status", "unknown"))

_show_page_links()

tab_overview, tab_collection, tab_fx, tab_quality = st.tabs(
    ["Overview", "BeautifulSoup collection", "Selenium exchange rates", "Data quality"]
)

with tab_overview:
    st.markdown("### Project overview")
    st.dataframe(_city_count_table(facilities_df), width = 'stretch', hide_index=True)
    st.markdown(
        """
        **City Explorer pages**에서는 문화시설 선택, 요일·시간 선택, 방문자 유형별 가격 조회,
        접근성 정보, 지도, 무료/저가 추천을 제공합니다.

        **Global Comparison Dashboard**에서는 USD 환산 입장료, 무료 시설 수, 학생·시니어 할인 비율,
        장애인 편의시설 비율, 야간 운영, 월요일 휴관 현황을 비교합니다.
        """
    )

with tab_collection:
    st.markdown("### BeautifulSoup data-collection design")
    st.write(
        "`scripts/collect_facility_sources_bs.py`는 `facilities.csv`의 `data_source` URL을 읽고, "
        "`requests`와 `BeautifulSoup`으로 공식 사이트 HTML을 파싱한 뒤 입장료·운영시간·접근성 관련 "
        "키워드 문장을 `data/raw_scraped_sources.csv`로 저장합니다."
    )
    scraped_df = load_raw_scraped_sources()
    if scraped_df.empty:
        st.warning("아직 raw BeautifulSoup 수집 결과가 없습니다. 터미널에서 아래 명령을 실행하세요.")
        st.code("python scripts/collect_facility_sources_bs.py", language="bash")
    else:
        st.metric("Scraped source rows", len(scraped_df))
        columns = [c for c in ["facility_id", "city", "name", "status_code", "keyword_count", "keywords_found", "error"] if c in scraped_df.columns]
        st.dataframe(scraped_df[columns], width = 'stretch', hide_index=True)
        st.download_button(
            "Download raw_scraped_sources.csv",
            scraped_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="raw_scraped_sources.csv",
            mime="text/csv",
        )

with tab_fx:
    st.markdown("### Selenium KITA exchange-rate collection")
    st.write(
        "`utils/exchange_rate.py`는 Selenium으로 KITA 환율종합 페이지를 열고, "
        "실시간 환율 표의 `매매기준율`에서 USD/KRW와 EUR/KRW를 읽습니다."
    )
    result = get_exchange_rates(use_live=True)
    st.dataframe(exchange_rates_to_dataframe(result), width = 'stretch', hide_index=True)
    if st.button("Refresh KITA exchange rates with Selenium", key="home_refresh_fx"):
        clear_exchange_rate_cache()
        _rerun()

with tab_quality:
    warnings = validate_data(facilities_df, opening_hours_df)
    if not warnings:
        st.success("No data-quality warnings.")
    else:
        for warning in warnings:
            st.warning(warning)
