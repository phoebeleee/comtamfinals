#지도(Folium): 문화시설 데이터를 기반으로 위치, 요금, 접근성 정보를 담은 지도 마커를 생성하고 Streamlit 화면에 렌더링

from __future__ import annotations

import html

import pandas as pd

from utils.price_utils import format_price, format_usd

try:
    import folium
except Exception as exc:  # pragma: no cover
    folium = None
    FOLIUM_IMPORT_ERROR = exc
else:
    FOLIUM_IMPORT_ERROR = None

try:
    from streamlit_folium import st_folium
except Exception:  # pragma: no cover
    st_folium = None


def _require_folium() -> None:
    if folium is None:
        raise ImportError("folium is required for map rendering") from FOLIUM_IMPORT_ERROR


def _valid_coordinates(row: pd.Series) -> bool:
    return not pd.isna(row.get("latitude")) and not pd.isna(row.get("longitude"))


def _access_text(row: pd.Series) -> str:
    items = []
    for column, label in [
        ("wheelchair_access", "Wheelchair"),
        ("accessible_restroom", "Restroom"),
        ("elevator", "Elevator"),
    ]:
        value = str(row.get(column, "UNKNOWN")).strip().upper()
        label_value = "Yes" if value == "TRUE" else "Partial" if value == "PARTIAL" else "No" if value == "FALSE" else "Unknown"
        items.append(f"{label}: {label_value}")
    return "<br>".join(items)


def make_popup_html(row: pd.Series) -> str:
    name = html.escape(str(row.get("name", "")))
    city = html.escape(str(row.get("city", "")))
    category = html.escape(str(row.get("category", "")))
    description = html.escape(str(row.get("description", "")))
    website = html.escape(str(row.get("website", "")))
    local_price = format_price(row.get("adult_price"), row.get("currency", ""))
    usd_price = format_usd(row.get("adult_price_usd"))
    link = f'<a href="{website}" target="_blank">Official website</a>' if website else ""
    return f"""
    <div style="font-family: Arial, sans-serif; width: 260px;">
        <h4 style="margin-bottom: 4px;">{name}</h4>
        <b>{city}</b> · {category}<br>
        <p style="margin: 8px 0;">{description}</p>
        <b>Adult fee:</b> {local_price} / {usd_price}<br>
        <b>Accessibility</b><br>{_access_text(row)}<br>
        {link}
    </div>
    """


def create_facilities_map(
    facilities_df: pd.DataFrame,
    selected_facility_id: str | None = None,
    zoom_start: int = 12,
):
    _require_folium()
    map_df = facilities_df[facilities_df.apply(_valid_coordinates, axis=1)].copy()
    if map_df.empty:
        raise ValueError("No valid coordinates found for map rendering")
    culture_map = folium.Map(
        location=[map_df["latitude"].mean(), map_df["longitude"].mean()],
        zoom_start=zoom_start,
        tiles="CartoDB positron",
    )
    for _, row in map_df.iterrows():
        is_selected = str(row.get("facility_id")) == str(selected_facility_id)
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(make_popup_html(row), max_width=340),
            tooltip=str(row.get("name", "")),
            icon=folium.Icon(color="red" if is_selected else "blue", icon="info-sign"),
        ).add_to(culture_map)
    return culture_map


def create_global_map(facilities_df: pd.DataFrame):
    _require_folium()
    map_df = facilities_df[facilities_df.apply(_valid_coordinates, axis=1)].copy()
    if map_df.empty:
        raise ValueError("No valid coordinates found for map rendering")
    culture_map = folium.Map(
        location=[map_df["latitude"].mean(), map_df["longitude"].mean()],
        zoom_start=3,
        tiles="CartoDB positron",
    )
    color_by_city = {"Seoul": "blue", "New York": "green", "Paris": "purple"}
    for _, row in map_df.iterrows():
        city = str(row.get("city", ""))
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(make_popup_html(row), max_width=340),
            tooltip=f"{row.get('name', '')} ({city})",
            icon=folium.Icon(color=color_by_city.get(city, "gray"), icon="info-sign"),
        ).add_to(culture_map)
    return culture_map


def _render_folium_map(culture_map, height: int, width: int | None = None):
    if st_folium is None:
        return culture_map
    try:
        return st_folium(culture_map, height=height, use_container_width=True, returned_objects=[])
    except TypeError:
        return st_folium(culture_map, width=width or 900, height=height)


def render_facilities_map(
    facilities_df: pd.DataFrame,
    selected_facility_id: str | None = None,
    height: int = 500,
    width: int | None = None,
):
    return _render_folium_map(
        create_facilities_map(facilities_df, selected_facility_id=selected_facility_id), height=height, width=width
    )


def render_global_map(facilities_df: pd.DataFrame, height: int = 560, width: int | None = None):
    return _render_folium_map(create_global_map(facilities_df), height=height, width=width)
