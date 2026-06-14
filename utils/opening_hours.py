#영업시간

from __future__ import annotations

from datetime import datetime, time
from typing import Any

import pandas as pd

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _is_true(value: Any) -> bool:
    return str(value).strip().upper() in {"TRUE", "YES", "Y", "1"}


def _parse_time(value: Any) -> time | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ["%H:%M", "%H:%M:%S"]:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _is_between(selected: time, start: time, end: time) -> bool:
    selected_min = _time_to_minutes(selected)
    start_min = _time_to_minutes(start)
    end_min = _time_to_minutes(end)
    if start_min <= end_min:
        return start_min <= selected_min <= end_min
    # Overnight schedule such as 18:00-01:00.
    return selected_min >= start_min or selected_min <= end_min


def get_day_schedule(opening_hours_df: pd.DataFrame, facility_id: str, day: str) -> pd.Series | None:
    matches = opening_hours_df[
        (opening_hours_df["facility_id"].astype(str) == str(facility_id))
        & (opening_hours_df["day"].astype(str) == str(day))
    ]
    if matches.empty:
        return None
    return matches.iloc[0]


def is_open_at(opening_hours_df: pd.DataFrame, facility_id: str, day: str, selected_time: str | time) -> bool:
    schedule = get_day_schedule(opening_hours_df, facility_id, day)
    if schedule is None or _is_true(schedule.get("is_closed")):
        return False
    selected = _parse_time(selected_time) if isinstance(selected_time, str) else selected_time
    open_time = _parse_time(schedule.get("open_time"))
    close_time = _parse_time(schedule.get("close_time"))
    if selected is None or open_time is None or close_time is None:
        return False
    return _is_between(selected, open_time, close_time)


def can_enter_at(opening_hours_df: pd.DataFrame, facility_id: str, day: str, selected_time: str | time) -> bool:
    schedule = get_day_schedule(opening_hours_df, facility_id, day)
    if schedule is None or not is_open_at(opening_hours_df, facility_id, day, selected_time):
        return False
    last_admission = _parse_time(schedule.get("last_admission"))
    if last_admission is None:
        return True
    selected = _parse_time(selected_time) if isinstance(selected_time, str) else selected_time
    open_time = _parse_time(schedule.get("open_time"))
    if selected is None or open_time is None:
        return False
    return _is_between(selected, open_time, last_admission)


def get_status_text(opening_hours_df: pd.DataFrame, facility_id: str, day: str, selected_time: str | time) -> str:
    schedule = get_day_schedule(opening_hours_df, facility_id, day)
    if schedule is None:
        return "No schedule data"
    if _is_true(schedule.get("is_closed")):
        return "Closed"
    if is_open_at(opening_hours_df, facility_id, day, selected_time):
        return "Open"
    return "Closed"


def format_schedule(schedule: pd.Series | None) -> str:
    if schedule is None:
        return "No schedule data"
    if _is_true(schedule.get("is_closed")):
        note = str(schedule.get("notes", "")).strip()
        return f"Closed ({note})" if note and note != "nan" else "Closed"
    open_time = str(schedule.get("open_time", "")).strip()
    close_time = str(schedule.get("close_time", "")).strip()
    last_admission = str(schedule.get("last_admission", "")).strip()
    result = f"{open_time} - {close_time}"
    if last_admission and last_admission.lower() != "nan":
        result += f"; last admission {last_admission}"
    note = str(schedule.get("notes", "")).strip()
    if note and note.lower() != "nan":
        result += f" ({note})"
    return result


def get_weekly_schedule(opening_hours_df: pd.DataFrame, facility_id: str) -> pd.DataFrame:
    df = opening_hours_df[opening_hours_df["facility_id"].astype(str) == str(facility_id)].copy()
    df["day"] = pd.Categorical(df["day"], categories=DAY_ORDER, ordered=True)
    return df.sort_values("day").reset_index(drop=True)
