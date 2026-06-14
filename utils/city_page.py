#서울, 파리, 뉴욕 도시별로 페이지 렌더링

from __future__ import annotations

from datetime import time

import pandas as pd
import streamlit as st

from utils.data_loader import get_facility_row, load_city_data, load_opening_hours_for_city
from utils.exchange_rate import clear_exchange_rate_cache
from utils.filters import (
    filter_accessible_facilities,
    filter_free_facilities,
    filter_open_facilities,
    get_top_cheapest_facilities,
)
from utils.map_utils import render_facilities_map
from utils.opening_hours import (
    DAY_ORDER,
    can_enter_at,
    format_schedule,
    get_day_schedule,
    get_status_text,
    get_weekly_schedule,
)
from utils.price_utils import add_effective_price_column, format_price, format_usd, get_price, get_visitor_types


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def _link_button(label: str, url: str) -> None:
    if not url:
        return
    if hasattr(st, "link_button"):
        st.link_button(label, url)
    else:
        st.markdown(f"[{label}]({url})")


def _access_label(value: object) -> str:
    text = str(value).strip().upper()
    if text == "TRUE":
        return "Yes"
    if text == "PARTIAL":
        return "Partial"
    if text == "FALSE":
        return "No"
    return "Unknown"


def _show_fx_caption(facilities_df: pd.DataFrame) -> None:
    fx = facilities_df.attrs.get("exchange_rate", {})
    if not fx:
        return
    usd = fx.get("usd_krw_rate")
    eur = fx.get("eur_krw_rate")
    status = fx.get("status", "")
    fetched_at = fx.get("fetched_at", "")
    st.caption(
        f"USD conversion uses KITA 매매기준율 via Selenium. "
        f"USD/KRW={usd}, EUR/KRW={eur}, status={status}, fetched_at={fetched_at}."
    )


def _format_table(df: pd.DataFrame, visitor_type: str) -> pd.DataFrame:
    """Return a compact table for Streamlit display."""
    if df.empty:
        return df

    table = add_effective_price_column(df, visitor_type, column_name="effective_price", usd=False)
    table = add_effective_price_column(table, visitor_type, column_name="effective_price_usd", usd=True)
    table["price_display"] = table.apply(
        lambda row: format_price(row["effective_price"], row.get("currency", "")), axis=1
    )
    table["price_usd_display"] = table["effective_price_usd"].apply(format_usd)

    columns = [
        "name",
        "category",
        "price_display",
        "price_usd_display",
        "wheelchair_access",
        "accessible_restroom",
        "elevator",
        "website",
    ]
    available_columns = [col for col in columns if col in table.columns]
    return table[available_columns].rename(
        columns={
            "name": "Facility",
            "category": "Category",
            "price_display": "Admission (local)",
            "price_usd_display": "Admission (USD)",
            "wheelchair_access": "Wheelchair",
            "accessible_restroom": "Accessible restroom",
            "elevator": "Elevator",
            "website": "Website",
        }
    )


def _show_accessibility_metrics(row: pd.Series) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Wheelchair access", _access_label(row.get("wheelchair_access")))
    col2.metric("Accessible restroom", _access_label(row.get("accessible_restroom")))
    col3.metric("Elevator", _access_label(row.get("elevator")))


def _show_facility_detail(
    facilities_df: pd.DataFrame,
    opening_hours_df: pd.DataFrame,
    selected_row: pd.Series,
    selected_day: str,
    selected_time: time,
    visitor_type: str,
) -> None:
    facility_id = str(selected_row["facility_id"])
    selected_time_text = selected_time.strftime("%H:%M")
    schedule = get_day_schedule(opening_hours_df, facility_id, selected_day)
    local_price = get_price(selected_row, visitor_type, usd=False)
    usd_price = get_price(selected_row, visitor_type, usd=True)
    status = get_status_text(opening_hours_df, facility_id, selected_day, selected_time_text)
    can_enter = can_enter_at(opening_hours_df, facility_id, selected_day, selected_time_text)

    st.subheader(selected_row["name"])
    st.write(selected_row.get("description", ""))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Open status", status)
    col2.metric("Admission (local)", format_price(local_price, selected_row.get("currency", "")))
    col3.metric("Admission (USD)", format_usd(usd_price))
    col4.metric("Entry status", "Entry available" if can_enter else "Entry unavailable")

    st.info(f"Schedule on {selected_day}: {format_schedule(schedule)}")
    _show_accessibility_metrics(selected_row)

    if selected_row.get("special_discount"):
        st.caption(f"Discount note: {selected_row.get('special_discount')}")
    if selected_row.get("free_entry_day"):
        st.caption(f"Free-entry note: {selected_row.get('free_entry_day')}")
    if selected_row.get("data_source"):
        st.caption(f"Data source: {selected_row.get('data_source')}")
    _link_button("Open official website", str(selected_row.get("website", "")))

    with st.expander("Weekly opening hours"):
        weekly = get_weekly_schedule(opening_hours_df, facility_id)
        st.dataframe(
            weekly[["day", "open_time", "close_time", "is_closed", "last_admission", "notes"]],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Map")
    render_facilities_map(facilities_df, selected_facility_id=facility_id, height=500)


def _show_recommendations(
    facilities_df: pd.DataFrame,
    opening_hours_df: pd.DataFrame,
    selected_day: str,
    selected_time: time,
    visitor_type: str,
) -> None:
    selected_time_text = selected_time.strftime("%H:%M")

    open_df = filter_open_facilities(facilities_df, opening_hours_df, selected_day, selected_time_text)
    free_df = filter_free_facilities(facilities_df, visitor_type)
    cheapest_df = get_top_cheapest_facilities(facilities_df, visitor_type, n=3)
    accessible_df = filter_accessible_facilities(facilities_df)

    st.markdown("### Quick recommendations")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Open now", len(open_df))
    col2.metric("Free for visitor", len(free_df))
    col3.metric("Accessible", len(accessible_df))
    col4.metric("Total", len(facilities_df))

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Open at selected time", "Free for me", "Cheapest TOP 3", "Accessible facilities"]
    )

    with tab1:
        if open_df.empty:
            st.warning("No facilities are open at the selected time.")
        else:
            st.dataframe(_format_table(open_df, visitor_type), use_container_width=True, hide_index=True)

    with tab2:
        if free_df.empty:
            st.warning("No free facilities for the selected visitor type.")
        else:
            st.dataframe(_format_table(free_df, visitor_type), use_container_width=True, hide_index=True)

    with tab3:
        st.dataframe(_format_table(cheapest_df, visitor_type), use_container_width=True, hide_index=True)

    with tab4:
        if accessible_df.empty:
            st.warning("No accessibility information available.")
        else:
            st.dataframe(_format_table(accessible_df, visitor_type), use_container_width=True, hide_index=True)


def render_city_explorer(city_name: str) -> None:
    """Render a complete city explorer page."""
    facilities_df = load_city_data(city_name, include_usd=True, use_live_rates=True)
    opening_hours_df = load_opening_hours_for_city(city_name)

    if facilities_df.empty:
        st.error(f"No facility data found for {city_name}.")
        return

    st.title(f"{city_name} Culture Explorer")
    st.caption("Check opening status, admission price, USD conversion, accessibility, recommendations, and maps.")
    _show_fx_caption(facilities_df)

    with st.sidebar:
        st.header(f"{city_name} options")
        if st.button("Refresh KITA exchange rates with Selenium", key=f"{city_name}_refresh_fx"):
            clear_exchange_rate_cache()
            _rerun()

        selected_name = st.selectbox("Facility", facilities_df["name"].tolist(), key=f"{city_name}_facility")
        selected_day = st.selectbox("Day", DAY_ORDER, index=0, key=f"{city_name}_day")
        selected_time = st.time_input("Time", value=time(14, 0), key=f"{city_name}_time")
        visitor_type = st.selectbox(
            "Visitor type", get_visitor_types(city_name), key=f"{city_name}_visitor_type"
        )

    selected_row = get_facility_row(facilities_df, selected_name)

    tab_detail, tab_recommend, tab_all_map = st.tabs(["Selected facility", "Recommendations", "All facilities map"])

    with tab_detail:
        button_clicked = st.button(
            "Check opening status and admission", key=f"{city_name}_check_button", type="primary"
        )
        if button_clicked:
            _show_facility_detail(
                facilities_df,
                opening_hours_df,
                selected_row,
                selected_day,
                selected_time,
                visitor_type,
            )
        else:
            st.write("Choose a facility, day, time, and visitor type in the sidebar, then click the check button.")
            st.markdown("#### Selected facility preview")
            st.write(selected_row.get("description", ""))
            local_price = get_price(selected_row, visitor_type, usd=False)
            usd_price = get_price(selected_row, visitor_type, usd=True)
            col1, col2 = st.columns(2)
            col1.metric("Admission preview (local)", format_price(local_price, selected_row.get("currency", "")))
            col2.metric("Admission preview (USD)", format_usd(usd_price))
            _link_button("Open official website", str(selected_row.get("website", "")))

    with tab_recommend:
        _show_recommendations(facilities_df, opening_hours_df, selected_day, selected_time, visitor_type)

    with tab_all_map:
        st.markdown(f"### {city_name} cultural facilities")
        render_facilities_map(facilities_df, selected_facility_id=str(selected_row["facility_id"]), height=560)
