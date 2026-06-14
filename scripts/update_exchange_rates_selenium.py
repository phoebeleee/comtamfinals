### 한국무역협회(KITA)에서 셀레니움으로 환율 가져오기. 
#### data/exchange_rates_cache.csv 으로 저장함 (생성형 AI 권장사항)

from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.exchange_rate import exchange_rates_to_dataframe, save_exchange_rates_cache, scrape_kita_exchange_rates_selenium


def main() -> None:
    result = scrape_kita_exchange_rates_selenium()
    path = save_exchange_rates_cache(result)
    print(f"Saved KITA exchange rates to {path}")
    print(exchange_rates_to_dataframe(result).to_string(index=False))


if __name__ == "__main__":
    main()
