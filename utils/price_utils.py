# 문화시설 입장료 (무료 여부 고려)

from __future__ import annotations

from typing import Mapping

import pandas as pd

PRICE_COLUMN_BY_VISITOR = {
    "adult": "adult_price",
    "general": "adult_price",
    "student": "student_price",
    "senior": "senior_price",
    "child": "child_price",
    "children": "child_price",
    "veteran": "veteran_price",
    "national merit": "veteran_price",
    "disabled": "disabled_price",
    "disability": "disabled_price",
    "eu under 26": "eu_under_26_price",
    "eu_under_26": "eu_under_26_price",
    "under 26": "eu_under_26_price",
}
VISITOR_TYPES_BY_CITY = {
    "Seoul": ["Adult", "Student", "Senior", "Child", "Veteran", "Disabled"],
    "New York": ["Adult", "Student", "Senior", "Child", "Disabled"],
    "Paris": ["Adult", "Student", "Senior", "Child", "EU under 26", "Disabled"],
}


def get_visitor_types(city: str | None = None) -> list[str]:
    if city is None:
        return ["Adult", "Student", "Senior", "Child", "Veteran", "Disabled", "EU under 26"]
    return VISITOR_TYPES_BY_CITY.get(city, VISITOR_TYPES_BY_CITY["New York"])


def get_price_column(visitor_type: str, usd: bool = False) -> str:
    column = PRICE_COLUMN_BY_VISITOR.get(str(visitor_type).strip().lower(), "adult_price")
    return f"{column}_usd" if usd else column


def _is_missing(value: object) -> bool:
    return value is None or pd.isna(value)


def get_price(
    row: Mapping[str, object] | pd.Series,
    visitor_type: str,
    fallback_to_adult: bool = True,
    usd: bool = False,
) -> float | None:
    price_column = get_price_column(visitor_type, usd=usd)
    value = row.get(price_column) if hasattr(row, "get") else None
    if _is_missing(value) and fallback_to_adult:
        value = row.get("adult_price_usd" if usd else "adult_price") if hasattr(row, "get") else None
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def add_effective_price_column(
    df: pd.DataFrame,
    visitor_type: str,
    column_name: str = "effective_price",
    usd: bool = False,
) -> pd.DataFrame:
    result = df.copy()
    result[column_name] = result.apply(lambda row: get_price(row, visitor_type, usd=usd), axis=1)
    return result


def format_price(price: object, currency: str = "") -> str:
    if price is None or pd.isna(price):
        return "No data"
    value = float(price)
    currency = str(currency).strip().upper()
    if value == 0:
        return "Free"
    if currency == "KRW":
        return f"KRW {value:,.0f}"
    if currency == "USD":
        return f"${value:,.2f}"
    if currency == "EUR":
        return f"€{value:,.2f}"
    return f"{value:,.2f} {currency}".strip()


def format_usd(price_usd: object) -> str:
    if price_usd is None or pd.isna(price_usd):
        return "No data"
    return f"${float(price_usd):,.2f}"


def is_free_for_visitor(row: Mapping[str, object] | pd.Series, visitor_type: str) -> bool:
    return get_price(row, visitor_type, usd=False) == 0


def has_discount(row: Mapping[str, object] | pd.Series, visitor_type: str) -> bool:
    visitor_price = get_price(row, visitor_type, fallback_to_adult=False)
    adult_price = get_price(row, "Adult")
    if visitor_price is None or adult_price is None:
        return False
    return visitor_price < adult_price
