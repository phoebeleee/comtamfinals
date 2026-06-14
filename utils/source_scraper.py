#BeautifulSoup으로 문화시설 공식 웹사이트에서 정보 수집

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import time
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup

DEFAULT_KEYWORDS = [
    "admission", "ticket", "fee", "price", "free", "student", "senior", "disabled",
    "accessibility", "accessible", "wheelchair", "opening", "hours", "closed", "last admission",
    "입장", "관람", "요금", "무료", "학생", "경로", "장애", "휠체어", "운영시간", "휴관",
    "tarif", "billet", "gratuit", "étudiant", "handicap", "accessibilité", "horaires", "fermé",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7,fr;q=0.6",
}


def _now_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def fetch_html(url: str, timeout: int = 20) -> tuple[str, int, str]:
    response = requests.get(str(url), headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text, int(response.status_code), str(response.url)


def extract_text_with_beautifulsoup(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form"]):
        tag.decompose()
    title = clean_whitespace(soup.title.get_text(" ")) if soup.title else ""
    content_nodes = soup.find_all(["main", "article"])
    if content_nodes:
        text = " ".join(node.get_text(" ", strip=True) for node in content_nodes)
    else:
        body = soup.body or soup
        text = body.get_text(" ", strip=True)
    return title, clean_whitespace(text)


def split_sentences(text: str) -> list[str]:
    normalized = clean_whitespace(text)
    chunks = re.split(r"(?<=[.!?。！？])\s+|\s{2,}|\|", normalized)
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) >= 20]


def extract_relevant_sentences(
    text: str,
    keywords: Iterable[str] = DEFAULT_KEYWORDS,
    max_sentences: int = 8,
) -> tuple[list[str], list[str]]:
    lowered_keywords = [keyword.lower() for keyword in keywords]
    found_keywords: set[str] = set()
    selected: list[str] = []
    for sentence in split_sentences(text):
        lower_sentence = sentence.lower()
        matched = [keyword for keyword in lowered_keywords if keyword in lower_sentence]
        if matched:
            found_keywords.update(matched)
            selected.append(sentence)
        if len(selected) >= max_sentences:
            break
    return selected, sorted(found_keywords)


def scrape_facility_source(row: pd.Series, timeout: int = 20) -> dict[str, object]:
    facility_id = str(row.get("facility_id", "")).strip()
    city = str(row.get("city", "")).strip()
    name = str(row.get("name", "")).strip()
    url = str(row.get("data_source", "")).strip() or str(row.get("website", "")).strip()
    result = {
        "facility_id": facility_id,
        "city": city,
        "name": name,
        "url": url,
        "status_code": None,
        "final_url": "",
        "page_title": "",
        "scraped_at": _now_kst(),
        "keyword_count": 0,
        "keywords_found": "",
        "relevant_text": "",
        "error": "",
    }
    if not url.startswith(("http://", "https://")):
        result["error"] = "Missing or invalid URL"
        return result
    try:
        html, status_code, final_url = fetch_html(url, timeout=timeout)
        title, text = extract_text_with_beautifulsoup(html)
        sentences, found_keywords = extract_relevant_sentences(text)
        result.update(
            {
                "status_code": status_code,
                "final_url": final_url,
                "page_title": title,
                "keyword_count": len(found_keywords),
                "keywords_found": ", ".join(found_keywords),
                "relevant_text": " || ".join(sentences),
            }
        )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def collect_sources_from_dataframe(
    facilities_df: pd.DataFrame,
    output_path: str | Path,
    delay_seconds: float = 0.5,
    timeout: int = 20,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, facility in facilities_df.iterrows():
        rows.append(scrape_facility_source(facility, timeout=timeout))
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    result_df = pd.DataFrame(rows)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output, index=False, encoding="utf-8-sig")
    return result_df
