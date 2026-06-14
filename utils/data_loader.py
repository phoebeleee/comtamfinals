#데이터 조회 (열분석, 생성형 AI 도움 받아 작성)

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from utils.exchange_rate import add_usd_columns, get_exchange_rates

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
FACILITIES_FILE = DATA_DIR / "facilities.csv"
OPENING_HOURS_FILE = DATA_DIR / "opening_hours.csv"
RAW_SCRAPED_SOURCES_FILE = DATA_DIR / "raw_scraped_sources.csv"

PRICE_COLUMNS = [
    "adult_price", "student_price", "senior_price", "child_price",
    "veteran_price", "disabled_price", "eu_under_26_price",
]
ACCESSIBILITY_COLUMNS = ["wheelchair_access", "accessible_restroom", "elevator"]
FACILITIES_REQUIRED_COLUMNS = [
    "facility_id", "city", "name", "category", "country", "currency",
    "latitude", "longitude", "website", "description",
]
OPENING_REQUIRED_COLUMNS = [
    "facility_id", "day", "open_time", "close_time", "is_closed", "last_admission", "notes",
]
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

try:
    import streamlit as st

    def cache_data(func):
        return st.cache_data(show_spinner=False)(func)

except Exception:  # pragma: no cover

    def cache_data(func):
        return func


def _as_path(path: str | Path | None, default_path: Path) -> Path:
    return default_path if path is None else Path(path)


def _require_columns(df: pd.DataFrame, required_columns: Iterable[str], file_label: str) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{file_label} is missing required columns: {missing}")


def _normalize_accessibility_value(value: object) -> str:
    if pd.isna(value):
        return "UNKNOWN"
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1"}:
        return "TRUE"
    if text in {"false", "no", "n", "0", "none", "nan", ""}:
        return "FALSE"
    if text in {"partial", "partly", "limited", "partially"}:
        return "PARTIAL"
    return text.upper()


def _normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "yes", "y", "1"}


def _normalize_day(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return {day.lower(): day for day in DAY_ORDER}.get(text.lower(), text)


@cache_data
def load_facilities_base(path: str | Path | None = None) -> pd.DataFrame:
    csv_path = _as_path(path, FACILITIES_FILE)
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find facilities file: {csv_path}")
    df = pd.read_csv(csv_path)
    _require_columns(df, FACILITIES_REQUIRED_COLUMNS, "facilities.csv")

    for column in PRICE_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    for column in ACCESSIBILITY_COLUMNS:
        if column in df.columns:
            df[column] = df[column].apply(_normalize_accessibility_value)
    if "night_opening" in df.columns:
        df["night_opening"] = df["night_opening"].apply(_normalize_bool)
    for column in ["latitude", "longitude"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    for column in [
        "facility_id", "city", "name", "category", "country", "currency", "website",
        "description", "free_entry_day", "special_discount", "data_source", "last_updated",
    ]:
        if column in df.columns:
            df[column] = df[column].fillna("").astype(str).str.strip()
    return df


def load_facilities(
    path: str | Path | None = None,
    include_usd: bool = True,
    use_live_rates: bool = True,
) -> pd.DataFrame:
    df = load_facilities_base(path).copy()
    if include_usd:
        exchange_result = get_exchange_rates(use_live=use_live_rates)
        df = add_usd_columns(df, exchange_result)
    return df


@cache_data
def load_opening_hours(path: str | Path | None = None) -> pd.DataFrame:
    csv_path = _as_path(path, OPENING_HOURS_FILE)
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find opening-hours file: {csv_path}")
    df = pd.read_csv(csv_path)
    _require_columns(df, OPENING_REQUIRED_COLUMNS, "opening_hours.csv")
    df["facility_id"] = df["facility_id"].fillna("").astype(str).str.strip()
    df["day"] = df["day"].apply(_normalize_day)
    df["is_closed"] = df["is_closed"].apply(_normalize_bool)
    for column in ["open_time", "close_time", "last_admission", "notes"]:
        df[column] = df[column].fillna("").astype(str).str.strip()
    df["day_order"] = df["day"].map({day: idx for idx, day in enumerate(DAY_ORDER)})
    return df.sort_values(["facility_id", "day_order"]).drop(columns=["day_order"])


def load_all_data(include_usd: bool = True, use_live_rates: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    return load_facilities(include_usd=include_usd, use_live_rates=use_live_rates), load_opening_hours()


def load_raw_scraped_sources(path: str | Path | None = None) -> pd.DataFrame:
    csv_path = _as_path(path, RAW_SCRAPED_SOURCES_FILE)
    if not csv_path.exists():
        return pd.DataFrame(columns=[
            "facility_id", "city", "name", "url", "status_code", "final_url", "page_title",
            "scraped_at", "keyword_count", "keywords_found", "relevant_text", "error",
        ])
    try:
        return pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def get_city_list(facilities_df: pd.DataFrame | None = None) -> list[str]:
    if facilities_df is None:
        facilities_df = load_facilities()
    preferred_order = ["Seoul", "New York", "Paris"]
    available = facilities_df["city"].dropna().unique().tolist()
    ordered = [city for city in preferred_order if city in available]
    ordered.extend(sorted(city for city in available if city not in ordered))
    return ordered


def load_city_data(city: str, include_usd: bool = True, use_live_rates: bool = True) -> pd.DataFrame:
    facilities_df = load_facilities(include_usd=include_usd, use_live_rates=use_live_rates)
    return facilities_df[facilities_df["city"].eq(city)].reset_index(drop=True)


def load_opening_hours_for_city(city: str) -> pd.DataFrame:
    city_facilities = load_facilities_base()
    city_facilities = city_facilities[city_facilities["city"].eq(city)]
    hours_df = load_opening_hours()
    return hours_df[hours_df["facility_id"].isin(city_facilities["facility_id"])].reset_index(drop=True)


def get_facility_row(facilities_df: pd.DataFrame, facility_name: str) -> pd.Series:
    matches = facilities_df[facilities_df["name"].eq(facility_name)]
    if matches.empty:
        raise ValueError(f"Unknown facility name: {facility_name}")
    return matches.iloc[0]


def merge_facilities_with_hours(
    facilities_df: pd.DataFrame | None = None,
    opening_hours_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if facilities_df is None:
        facilities_df = load_facilities()
    if opening_hours_df is None:
        opening_hours_df = load_opening_hours()
    return opening_hours_df.merge(facilities_df, on="facility_id", how="left")


def validate_data(
    facilities_df: pd.DataFrame | None = None,
    opening_hours_df: pd.DataFrame | None = None,
) -> list[str]:
    if facilities_df is None:
        facilities_df = load_facilities()
    if opening_hours_df is None:
        opening_hours_df = load_opening_hours()
    warnings: list[str] = []
    duplicated_ids = facilities_df[facilities_df["facility_id"].duplicated()]["facility_id"].tolist()
    if duplicated_ids:
        warnings.append(f"Duplicated facility_id values: {duplicated_ids}")
    missing_hours = set(facilities_df["facility_id"]) - set(opening_hours_df["facility_id"])
    if missing_hours:
        warnings.append(f"Facilities without opening-hour rows: {sorted(missing_hours)}")
    for facility_id, group in opening_hours_df.groupby("facility_id"):
        missing_days = set(DAY_ORDER) - set(group["day"])
        if missing_days:
            warnings.append(f"{facility_id} is missing opening-hour rows for: {sorted(missing_days)}")
    missing_coordinates = facilities_df[facilities_df[["latitude", "longitude"]].isna().any(axis=1)]
    if not missing_coordinates.empty:
        warnings.append(f"Facilities with missing coordinates: {missing_coordinates['facility_id'].tolist()}")
    if "adult_price_usd" not in facilities_df.columns:
        warnings.append("USD price columns are missing. Check exchange-rate loading.")
    return warnings
