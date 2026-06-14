## USD 환율 저장
###결과물 저장: data/facilities_with_usd_snapshot.csv


from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.data_loader import DATA_DIR, load_facilities


def main() -> None:
    facilities_df = load_facilities(include_usd=True, use_live_rates=True)
    output_path = DATA_DIR / "facilities_with_usd_snapshot.csv"
    facilities_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    fx = facilities_df.attrs.get("exchange_rate", {})
    print(f"Saved {len(facilities_df)} rows to {output_path}")
    print(f"FX status: {fx.get('status')} | USD/KRW={fx.get('usd_krw_rate')} | EUR/KRW={fx.get('eur_krw_rate')}")


if __name__ == "__main__":
    main()
