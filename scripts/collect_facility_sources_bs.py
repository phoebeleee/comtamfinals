### 시설별 정보 수집하는 코드, BeautifulSoup 사용
### 결과물 저장: data/raw_scraped_sources.csv
### 웹사이트 접근 불가 등으로 스크래핑에 실패한 항목은 수작업으로 보완하여 facilities.csv에 저장했습니다

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.data_loader import RAW_SCRAPED_SOURCES_FILE, load_facilities_base
from utils.source_scraper import collect_sources_from_dataframe


def main() -> None:
    facilities_df = load_facilities_base()
    result_df = collect_sources_from_dataframe(
        facilities_df,
        output_path=RAW_SCRAPED_SOURCES_FILE,
        delay_seconds=0.5,
        timeout=20,
    )
    success_count = int(result_df["error"].fillna("").eq("").sum()) if "error" in result_df.columns else 0
    print(f"Saved {len(result_df)} rows to {RAW_SCRAPED_SOURCES_FILE}")
    print(f"Successful requests: {success_count}; failed requests: {len(result_df) - success_count}")


if __name__ == "__main__":
    main()

