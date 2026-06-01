# 📈 StockView — 주가 예측 실험실

한국 주식(KOSPI/KOSDAQ)과 미국 주식(NASDAQ/NYSE)을 머신러닝으로 분석하는 **학습용** 웹 앱입니다.1
종목을 검색하면 가격 차트와 함께, "다음 거래일 상승/하락"을 예측하는
ML 모델의 결과 **그리고 그 모델이 실제로 믿을 만한지** 보여줍니다.

> ⚠️ **솔직한 안내**: 단기 주가 방향 예측은 원리적으로 매우 어렵습니다(정확도 50%대).
> 이 앱은 돈을 버는 도구가 아니라, "주가 예측이 왜 어려운지"를 직접 데이터로
> 체험하는 교육용 도구입니다. 그래서 모델 정확도를 항상 **베이스라인(무조건 다수
> 방향에 베팅)**과 비교해 정직하게 표시합니다.

## 구조

```
StockView/
├── backend/          # Python + FastAPI
│   ├── data.py       # FinanceDataReader로 한국+미국 주식 데이터 수집
│   ├── features.py   # 기술적 지표 → ML 피처 (이동평균, RSI, 변동성 등)
│   ├── model.py      # RandomForest 학습 / 예측 / 시간순 백테스트
│   └── main.py       # API 엔드포인트
└── frontend/         # React (Vite) + Recharts
    └── src/
        ├── App.jsx
        └── components/  # SearchBar, PriceChart, PredictionPanel
```

## 실행 방법

### 가장 간단 — `make` (권장)

```bash
make install   # 최초 1회: 백엔드 venv + 프론트 node_modules 설치
make           # 백엔드(:8000) + 프론트(:5173) 동시 실행, Ctrl-C로 둘 다 종료
```

브라우저에서 **http://localhost:5173** 접속.

| 명령 | 설명 |
|------|------|
| `make` (= `make dev`) | 백엔드 + 프론트 **동시 실행** |
| `make backend`  | 백엔드만 (코드 변경 시 자동 리로드) |
| `make frontend` | 프론트만 |
| `make install`  | 의존성 설치 |
| `make clean`    | venv / node_modules 삭제 |

> Windows에 `make`가 없다면: `winget install ezwinports.make` 설치 후 **터미널을 새로 열면** `make`가 잡힙니다.
> Makefile은 셸을 Git Bash로 고정하므로 Git이 설치돼 있어야 합니다.

### 수동 실행 (make 없이, 터미널 2개)

```powershell
# 터미널 1 — 백엔드
cd backend
./venv/Scripts/python.exe -m uvicorn main:app --port 8000 --host 127.0.0.1

# 터미널 2 — 프론트엔드
cd frontend
npm run dev
```

(최초 설치: `cd backend && python -m venv venv && ./venv/Scripts/python.exe -m pip install -r requirements.txt`,
그리고 `cd frontend && npm install`)

## API

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/search?q=삼성` | 종목명/코드 검색 (한국+미국, 예: `삼성`, `AAPL`) |
| `GET /api/stock/{code}`  | 일봉 OHLCV 시세 (차트용) |
| `GET /api/predict/{code}`| ML 예측 + 백테스트 평가 지표 |
| `GET /api/preview/{code}`| 목록용 빠른 예측 (방향+확률만) |
| `GET /api/news/{code}`   | 최근 뉴스 헤드라인 (한국=네이버, 미국=구글 뉴스) |
| `GET /api/lists`         | 추천 목록 카탈로그 |
| `GET /api/list/{id}`     | 목록별 종목 (예: `krx_cap100`, `us_cap100`, `krx_gainers`) |

## 모델이 하는 일

1. 과거 일봉 데이터에서 피처를 만든다 — 단기/중기 수익률, 이동평균 대비 위치,
   변동성, 거래량 변화, RSI, 최근 가격대 내 위치 등.
2. "다음날 종가가 오늘보다 높은가?"를 타깃으로 RandomForest를 학습.
3. **시간순으로** 앞 80%로 학습, 뒤 20%로 검증 (시계열이므로 절대 셔플하지 않음).
4. 검증 정확도를 베이스라인과 비교해 `edge`(우위)를 계산 →
   edge가 0보다 커야 모델이 의미가 있는 것.

## 커밋 컨벤션

커밋 메시지는 [Conventional Commits](https://www.conventionalcommits.org/) 형식을 따릅니다.
자세한 규칙·예시는 [COMMIT_CONVENTION.md](COMMIT_CONVENTION.md) 참고.
클론 후 한 번 `git config commit.template .gitmessage` 를 실행하면 커밋 시 양식이 자동으로 뜹니다.

## 다음으로 해볼 만한 것

- 모델 비교: 로지스틱회귀 / XGBoost / LSTM 추가하고 성능 비교
- 백테스트 강화: "이 신호로 매매했다면 수익률은?" 시뮬레이션
- 피처 추가: 거시지표(환율, 금리), 외국인/기관 수급, 뉴스 감성
- walk-forward 검증으로 더 엄밀하게 평가
