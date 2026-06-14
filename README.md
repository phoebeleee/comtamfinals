# 문화의 문턱: 전세계 문화 접근성 비교 분석

서울, 뉴욕, 파리의 대표 문화시설 30곳을 대상으로 운영시간, 방문자 유형별 입장료, 장애인 접근성, 지도, 도시별 비교 대시보드를 제공하는 Streamlit 웹앱입니다.

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run main.py
```

## 데이터 수집 코드

### 1. BeautifulSoup 공식 사이트 원문 수집

```bash
python scripts/collect_facility_sources_bs.py
```

- 입력: `data/facilities.csv`의 `data_source` URL
- 처리: `requests`로 HTML 다운로드, `BeautifulSoup`으로 HTML 파싱, 입장료/운영시간/접근성 키워드 문장 추출
- 출력: `data/raw_scraped_sources.csv`

### 2. Selenium KITA 실시간 환율 수집

```bash
python scripts/update_exchange_rates_selenium.py
```

- 입력: 한국무역협회 KITA 환율종합 페이지
- 처리: Selenium headless Chrome으로 페이지 접속, 실시간 환율 표의 `매매기준율`에서 USD/KRW와 EUR/KRW 추출
- 출력: `data/exchange_rates_cache.csv`

### 3. USD 환산 컬럼 스냅샷 생성

```bash
python scripts/build_usd_facility_snapshot.py
```

- 입력: `data/facilities.csv`, KITA 환율
- 출력: `data/facilities_with_usd_snapshot.csv`

## USD 환산 공식

KITA의 `매매기준율`은 KRW per currency unit 값입니다.

- KRW 가격 → USD: `KRW price / USD_KRW`
- EUR 가격 → USD: `EUR price * EUR_KRW / USD_KRW`
- USD 가격 → USD: 그대로 사용

## 제출 보고서에 설명할 핵심

- Streamlit 앱은 실시간 크롤링 결과에만 의존하지 않고, 안정성을 위해 정제 CSV를 기본 데이터로 사용합니다.
- BeautifulSoup 코드는 공식 사이트 원문 수집과 데이터 검증 근거를 남기는 데 사용됩니다.
- Selenium 코드는 KITA 실시간 환율 페이지에서 `매매기준율`을 읽어 USD 환산 컬럼을 만드는 데 사용됩니다.
- Selenium/Chrome 환경이 불안정할 수 있으므로 앱은 live scrape 실패 시 `exchange_rates_cache.csv`를 fallback으로 사용합니다.
