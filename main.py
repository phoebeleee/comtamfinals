from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.data_loader import load_all_data, validate_data
from utils.exchange_rate import clear_exchange_rate_cache

st.set_page_config(
    page_title="Global Culture Access Explorer",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


st.title("문화의 문턱: 세계 주요 도시의 문화시설 접근성 분석")
st.caption("서울 · 뉴욕 · 파리 문화시설 접근성 분석 플랫폼")

try:
    facilities_df, opening_hours_df = load_all_data(include_usd=True, use_live_rates=True)
except Exception as exc:
    st.error("데이터 파일을 불러오지 못했습니다. `data/` 폴더 구성을 확인하세요.")
    st.exception(exc)
    st.stop()

fx = facilities_df.attrs.get("exchange_rate", {})

col1, col2, col3, col4 = st.columns(4)
col1.metric("Cities", facilities_df["city"].nunique())
col2.metric("Facilities", len(facilities_df))
col3.metric("Opening-hour rows", len(opening_hours_df))
col4.metric("FX status", fx.get("status", "unknown"))

st.markdown(
    """
    서울, 뉴욕, 파리의 대표 문화시설 각 10곳을 대상으로 다음 질문에 답합니다.

    - 선택한 요일과 시간에 문화시설이 열려 있는가?
    - 방문자 유형별 최저 입장료는 얼마인가?
    - 입장료를 KITA 실시간 환율의 **매매기준율**로 USD 환산하면 얼마인가?
    - 장애인 편의시설과 접근성 정보는 어떤가?
    - 도시별 무료 시설, 할인 비율, 야간 운영, 월요일 휴관 패턴은 어떻게 다른가?
    """
)

st.info(
    "왼쪽 사이드바의 Pages 메뉴에서 Home, Seoul Explorer, New York Explorer, Paris Explorer, "
    "Global Comparison Dashboard로 이동하세요."
)

with st.expander("Exchange-rate status", expanded=True):
    st.write(
        {
            "source": fx.get("source_url"),
            "source_method": fx.get("source_method"),
            "status": fx.get("status"),
            "USD/KRW": fx.get("usd_krw_rate"),
            "EUR/KRW": fx.get("eur_krw_rate"),
            "fetched_at": fx.get("fetched_at"),
            "message": fx.get("message"),
        }
    )
    if st.button("Refresh KITA exchange rates with Selenium"):
        clear_exchange_rate_cache()
        _rerun()

warnings = validate_data(facilities_df, opening_hours_df)
if warnings:
    with st.expander("Data quality warnings"):
        for warning in warnings:
            st.warning(warning)
