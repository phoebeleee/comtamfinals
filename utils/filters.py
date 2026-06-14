# 문화시설 필터/요약 기능 (웹페이지에서 테이블로 조회할 때)

from __future__ import annotations

import pandas as pd

from utils.opening_hours import is_open_at
from utils.price_utils import add_effective_price_column, get_price, has_discount, is_free_for_visitor

ACCESSIBILITY_COLUMNS = ["wheelchair_access", "accessible_restroom", "elevator"]


def _is_positive_accessibility(value: object) -> bool:
    return str(value).strip().upper() in {"TRUE", "PARTIAL"}


def has_accessibility_feature(row: pd.Series) -> bool:
    return any(_is_positive_accessibility(row.get(column)) for column in ACCESSIBILITY_COLUMNS)


def filter_accessible_facilities(facilities_df: pd.DataFrame) -> pd.DataFrame:
    if facilities_df.empty:
        return facilities_df.copy()
    return facilities_df[facilities_df.apply(has_accessibility_feature, axis=1)].reset_index(drop=True)


def filter_free_facilities(facilities_df: pd.DataFrame, visitor_type: str) -> pd.DataFrame:
    if facilities_df.empty:
        return facilities_df.copy()
    return facilities_df[facilities_df.apply(lambda row: is_free_for_visitor(row, visitor_type), axis=1)].reset_index(drop=True)


def filter_open_facilities(
    facilities_df: pd.DataFrame,
    opening_hours_df: pd.DataFrame,
    selected_day: str,
    selected_time: str,
) -> pd.DataFrame:
    if facilities_df.empty:
        return facilities_df.copy()
    mask = facilities_df["facility_id"].apply(
        lambda facility_id: is_open_at(opening_hours_df, str(facility_id), selected_day, selected_time)
    )
    return facilities_df[mask].reset_index(drop=True)


def get_top_cheapest_facilities(facilities_df: pd.DataFrame, visitor_type: str, n: int = 3) -> pd.DataFrame:
    priced = add_effective_price_column(facilities_df, visitor_type, column_name="effective_price", usd=False)
    priced = add_effective_price_column(priced, visitor_type, column_name="effective_price_usd", usd=True)
    return priced.sort_values(["effective_price_usd", "effective_price", "name"], na_position="last").head(n).reset_index(drop=True)


def _ratio(series: pd.Series) -> float:
    return 0.0 if len(series) == 0 else float(series.mean())


def _monday_closed_counts(opening_hours_df: pd.DataFrame | None) -> pd.DataFrame:
    if opening_hours_df is None or opening_hours_df.empty:
        return pd.DataFrame(columns=["facility_id", "monday_closed"])
    monday = opening_hours_df[opening_hours_df["day"].eq("Monday")].copy()
    if monday.empty:
        return pd.DataFrame(columns=["facility_id", "monday_closed"])
    monday["monday_closed"] = monday["is_closed"].astype(bool)
    return monday[["facility_id", "monday_closed"]]


def build_city_summary(
    facilities_df: pd.DataFrame,
    opening_hours_df: pd.DataFrame | None = None,
    visitor_type: str = "Adult",
) -> pd.DataFrame:
    if facilities_df.empty:
        return pd.DataFrame()

    df = facilities_df.copy()
    df = add_effective_price_column(df, visitor_type, column_name="effective_price", usd=False)
    df = add_effective_price_column(df, visitor_type, column_name="effective_price_usd", usd=True)
    df["free_for_selected"] = df.apply(lambda row: get_price(row, visitor_type, usd=False) == 0, axis=1)
    df["student_discount"] = df.apply(lambda row: has_discount(row, "Student"), axis=1)
    df["senior_discount"] = df.apply(lambda row: has_discount(row, "Senior"), axis=1)
    df["has_accessibility"] = df.apply(has_accessibility_feature, axis=1)

    monday_counts = _monday_closed_counts(opening_hours_df)
    if not monday_counts.empty:
        df = df.merge(monday_counts, on="facility_id", how="left")
    else:
        df["monday_closed"] = False
    df["monday_closed"] = df["monday_closed"].fillna(False).astype(bool)

    summary = (
        df.groupby("city")
        .agg(
            facility_count=("facility_id", "count"),
            average_adult_price_local=("adult_price", "mean"),
            average_adult_price_usd=("adult_price_usd", "mean"),
            average_selected_price_local=("effective_price", "mean"),
            average_selected_price_usd=("effective_price_usd", "mean"),
            free_count=("free_for_selected", "sum"),
            student_discount_ratio=("student_discount", _ratio),
            senior_discount_ratio=("senior_discount", _ratio),
            accessibility_ratio=("has_accessibility", _ratio),
            night_opening_count=("night_opening", "sum"),
            monday_closed_count=("monday_closed", "sum"),
        )
        .reset_index()
    )
    for column in [
        "average_adult_price_local", "average_adult_price_usd",
        "average_selected_price_local", "average_selected_price_usd",
        "student_discount_ratio", "senior_discount_ratio", "accessibility_ratio",
    ]:
        summary[column] = pd.to_numeric(summary[column], errors="coerce").round(3)
    for column in ["facility_count", "free_count", "night_opening_count", "monday_closed_count"]:
        summary[column] = summary[column].fillna(0).astype(int)
    return summary
