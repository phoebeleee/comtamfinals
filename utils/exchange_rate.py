# 셀레니움으로 KITA 한국무역협회의 실시간 환율 정보 가져오기 (미국 달러 기준으로 환산함)
# KITA '매매기준율', https://www.kita.net/cmmrcInfo/ehgtGnrlzInfo/rltmEhgt.do

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_FILE = DATA_DIR / "exchange_rates_cache.csv"
KITA_EXCHANGE_URL = "https://www.kita.net/cmmrcInfo/ehgtGnrlzInfo/rltmEhgt.do"

FALLBACK_RATES = {"USD": 1520.70, "EUR": 1760.51, "KRW": 1.0}
PRICE_COLUMNS = [
    "adult_price",
    "student_price",
    "senior_price",
    "child_price",
    "veteran_price",
    "disabled_price",
    "eu_under_26_price",
]

try:
    import streamlit as st

    def cache_data(func):
        return st.cache_data(ttl=60 * 60, show_spinner=False)(func)

except Exception:  # pragma: no cover

    def cache_data(func):
        return func


@dataclass(frozen=True)
class ExchangeRateResult:
    """Exchange-rate values plus scraping metadata.

    rates are KRW per 1 unit of each currency. Example: rates["USD"] = 1520.70.
    """

    rates: dict[str, float]
    fetched_at: str
    source_url: str
    source_method: str
    status: str
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["usd_krw_rate"] = self.rates.get("USD")
        data["eur_krw_rate"] = self.rates.get("EUR")
        return data


class ExchangeRateError(RuntimeError):
    """Raised when live exchange-rate scraping fails."""


def _now_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")


def parse_number(text: str) -> float:
    return float(str(text).strip().replace(",", ""))


def _extract_rates_from_text(text: str, target_currencies: tuple[str, ...] = ("USD", "EUR")) -> dict[str, float]:
    rates: dict[str, float] = {}
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]

    for code in target_currencies:
        for line in lines:
            if not line.startswith(code):
                continue
            numbers = re.findall(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?", line)
            if numbers:
                rates[code] = parse_number(numbers[0])
                break

    for code in target_currencies:
        if code in rates:
            continue
        pattern = rf"\b{code}\b\s+[^\d\n\r]*?\s+(\d{{1,3}}(?:,\d{{3}})*(?:\.\d+)?)"
        match = re.search(pattern, text)
        if match:
            rates[code] = parse_number(match.group(1))

    missing = [code for code in target_currencies if code not in rates]
    if missing:
        raise ExchangeRateError(f"Could not extract KITA mid rates for: {missing}")

    rates["KRW"] = 1.0
    return rates


def _extract_posted_date(text: str) -> str | None:
    match = re.search(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", str(text))
    if not match:
        return None
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _build_chrome_driver(options):
    """Build a Chrome driver across local, Colab, and Streamlit Cloud setups."""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service

    for binary in [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]:
        if Path(binary).exists():
            options.binary_location = binary
            break

    for driver_path in [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/opt/homebrew/bin/chromedriver",
    ]:
        if Path(driver_path).exists():
            return webdriver.Chrome(service=Service(driver_path), options=options)

    return webdriver.Chrome(options=options)


def scrape_kita_exchange_rates_selenium(timeout: int = 25) -> ExchangeRateResult:
    """Fetch USD and EUR 매매기준율 values from KITA using Selenium."""
    try:
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
    except Exception as exc:  # pragma: no cover
        raise ExchangeRateError(f"Selenium is not installed or not importable: {exc}") from exc

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,1200")
    options.add_argument("--lang=ko-KR")

    driver = None
    try:
        driver = _build_chrome_driver(options)
        driver.get(KITA_EXCHANGE_URL)
        WebDriverWait(driver, timeout).until(
            lambda d: "매매기준율" in d.page_source and "USD" in d.page_source and "EUR" in d.page_source
        )
        body_text = driver.find_element(By.TAG_NAME, "body").text
        rates = _extract_rates_from_text(body_text)
        posted_date = _extract_posted_date(body_text)
        message = "Live Selenium scrape succeeded."
        if posted_date:
            message += f" KITA posted date: {posted_date}."
        return ExchangeRateResult(
            rates=rates,
            fetched_at=_now_kst(),
            source_url=KITA_EXCHANGE_URL,
            source_method="selenium",
            status="live",
            message=message,
        )
    except Exception as exc:
        raise ExchangeRateError(f"KITA Selenium scraping failed: {exc}") from exc
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def save_exchange_rates_cache(result: ExchangeRateResult, path: str | Path | None = None) -> Path:
    cache_path = Path(path) if path is not None else CACHE_FILE
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for currency, rate in result.rates.items():
        rows.append(
            {
                "currency": currency,
                "mid_rate_krw": rate,
                "source_url": result.source_url,
                "fetched_at": result.fetched_at,
                "source_method": result.source_method,
                "status": result.status,
                "message": result.message,
            }
        )
    pd.DataFrame(rows).sort_values("currency").to_csv(cache_path, index=False, encoding="utf-8-sig")
    return cache_path


def load_exchange_rates_cache(path: str | Path | None = None) -> ExchangeRateResult:
    cache_path = Path(path) if path is not None else CACHE_FILE
    if not cache_path.exists():
        raise FileNotFoundError(f"Exchange-rate cache not found: {cache_path}")
    df = pd.read_csv(cache_path)
    if df.empty:
        raise ValueError(f"Exchange-rate cache is empty: {cache_path}")
    required = {"currency", "mid_rate_krw"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Exchange-rate cache missing columns: {sorted(missing)}")
    rates = {
        str(row["currency"]).strip().upper(): float(row["mid_rate_krw"])
        for _, row in df.dropna(subset=["currency", "mid_rate_krw"]).iterrows()
    }
    rates.setdefault("KRW", 1.0)
    if "USD" not in rates:
        raise ValueError("Exchange-rate cache must contain USD.")
    first = df.iloc[0]
    return ExchangeRateResult(
        rates=rates,
        fetched_at=str(first.get("fetched_at", "")),
        source_url=str(first.get("source_url", KITA_EXCHANGE_URL)),
        source_method=str(first.get("source_method", "cache")),
        status=str(first.get("status", "cache")),
        message=str(first.get("message", "Loaded from exchange_rates_cache.csv.")),
    )


def _fallback_result(message: str) -> ExchangeRateResult:
    return ExchangeRateResult(
        rates=dict(FALLBACK_RATES),
        fetched_at="2026-06-12 00:00:00 KST",
        source_url=KITA_EXCHANGE_URL,
        source_method="fallback_constant",
        status="fallback",
        message=message,
    )


@cache_data
def get_exchange_rates(use_live: bool = True) -> ExchangeRateResult:
    """Return live Selenium rates when possible, otherwise cache/fallback rates."""
    if use_live:
        try:
            result = scrape_kita_exchange_rates_selenium()
            save_exchange_rates_cache(result)
            return result
        except Exception as exc:
            selenium_error = str(exc)
            try:
                cached = load_exchange_rates_cache()
                return ExchangeRateResult(
                    rates=cached.rates,
                    fetched_at=cached.fetched_at,
                    source_url=cached.source_url,
                    source_method=cached.source_method,
                    status="cache_after_selenium_failure",
                    message=f"Selenium failed; loaded cached KITA rates. Error: {selenium_error}",
                )
            except Exception as cache_exc:
                return _fallback_result(
                    f"Selenium and cache both failed. Selenium error: {selenium_error}; cache error: {cache_exc}"
                )
    try:
        return load_exchange_rates_cache()
    except Exception as exc:
        return _fallback_result(f"Cache load failed; using fallback rates. Error: {exc}")


def clear_exchange_rate_cache() -> None:
    if hasattr(get_exchange_rates, "clear"):
        get_exchange_rates.clear()  # type: ignore[attr-defined]


def convert_price_to_usd(amount: Any, currency: str, rates: dict[str, float]) -> float | None:
    if amount is None or pd.isna(amount):
        return None
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    currency = str(currency).strip().upper()
    usd_krw = float(rates.get("USD", FALLBACK_RATES["USD"]))
    if currency == "USD":
        return round(value, 2)
    if currency == "KRW":
        return round(value / usd_krw, 2)
    if currency == "EUR":
        eur_krw = float(rates.get("EUR", FALLBACK_RATES["EUR"]))
        return round((value * eur_krw) / usd_krw, 2)
    return None


def add_usd_columns(facilities_df: pd.DataFrame, result: ExchangeRateResult | None = None) -> pd.DataFrame:
    df = facilities_df.copy()
    if result is None:
        result = get_exchange_rates(use_live=True)
    for column in PRICE_COLUMNS:
        if column not in df.columns:
            continue
        usd_column = f"{column}_usd"
        df[usd_column] = df.apply(
            lambda row, col=column: convert_price_to_usd(row.get(col), row.get("currency", ""), result.rates),
            axis=1,
        )
    df["usd_krw_rate"] = result.rates.get("USD")
    df["eur_krw_rate"] = result.rates.get("EUR")
    df["fx_fetched_at"] = result.fetched_at
    df["fx_source_method"] = result.source_method
    df["fx_status"] = result.status
    df.attrs["exchange_rate"] = result.to_dict()
    return df


def exchange_rates_to_dataframe(result: ExchangeRateResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "currency": currency,
                "mid_rate_krw": rate,
                "source_url": result.source_url,
                "fetched_at": result.fetched_at,
                "source_method": result.source_method,
                "status": result.status,
                "message": result.message,
            }
            for currency, rate in sorted(result.rates.items())
        ]
    )
