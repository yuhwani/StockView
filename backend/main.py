"""StockView 백엔드 API (FastAPI).

엔드포인트:
  GET /api/search?q=...          종목 검색
  GET /api/stock/{code}          OHLCV 시세 (차트용)
  GET /api/predict/{code}        ML 예측 + 백테스트 평가
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import dart
import data
import fundamentals
import model as ml
import news as news_mod
import sentiment

app = FastAPI(title="StockView API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 학습용 로컬 환경이라 전체 허용
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/search")
def search(q: str):
    return {"results": data.search_stocks(q)}


@app.get("/api/lists")
def lists():
    """사용 가능한 추천 목록 카탈로그."""
    return {"lists": data.list_catalog()}


@app.get("/api/list/{list_id}")
def named_list(list_id: str, limit: int = 100):
    try:
        items = data.get_named_list(list_id, limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"id": list_id, "items": items}


@app.get("/api/stock/{code}")
def stock(code: str, start: str = "2018-01-01", refresh: int = 0):
    try:
        df = data.get_ohlcv(code, start, force=bool(refresh))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 미국 데이터는 인덱스 이름이 없을 수 있어 강제로 'Date'로 지정
    df.index.name = "Date"
    df = df.reset_index()
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    candles = df[["Date", "Open", "High", "Low", "Close", "Volume"]].to_dict(
        orient="records"
    )
    return {
        "code": code,
        "name": data.get_name(code),
        "region": data.get_region(code),
        "as_of": candles[-1]["Date"] if candles else None,  # 데이터 기준일(마지막 거래일)
        "candles": candles,
    }


@app.get("/api/preview/{code}")
def preview(code: str):
    """목록용 빠른 예측 미리보기 (방향+확률만)."""
    try:
        df = data.get_ohlcv(code)
        pred = ml.quick_predict(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": code, "prediction": pred}


@app.get("/api/news/{code}")
def news(code: str, refresh: int = 0):
    """종목 관련 최근 뉴스 헤드라인 (한국=네이버, 미국=구글 뉴스)."""
    region = data.get_region(code)
    name = data.get_name(code) or code
    items = news_mod.get_news(code, region, name, force=bool(refresh))
    return {"code": code, "region": region, "items": items}


@app.get("/api/forecast/{code}")
def forecast(code: str, refresh: int = 0):
    """다기간 미래 주가 예측 (하루·일주일·한달·장기)."""
    try:
        df = data.get_ohlcv(code, force=bool(refresh))
        result = ml.forecast(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result["code"] = code
    result["region"] = data.get_region(code)
    return result


@app.get("/api/backtest/{code}")
def backtest(code: str, refresh: int = 0):
    """ML 예측대로 매매했을 때 수익률 백테스트 (단순보유 대비)."""
    try:
        df = data.get_ohlcv(code, force=bool(refresh))
        result = ml.backtest(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result["code"] = code
    return result


@app.get("/api/predict/{code}")
def predict(code: str, refresh: int = 0):
    region = data.get_region(code)
    name = data.get_name(code)
    force = bool(refresh)
    try:
        df = data.get_ohlcv(code, force=force)
        # 펀더멘털·수급·뉴스 감성을 모아 판단 신호에 반영 (실패해도 가격 기반으로 진행)
        fund = fundamentals.get_fundamentals(code, region, force=force)
        sent = sentiment.analyze(news_mod.get_news(code, region, name, force=force))
        dart_events = dart.detect_events(code)  # 한국 종목 실제 공시 재료
        extras = {
            "valuation": fund,
            "supply": fund.get("supply"),
            "sentiment": sent,
            "dart_events": dart_events,
            "region": region,
        }
        result = ml.train_and_evaluate(df, extras)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result["code"] = code
    result["name"] = name
    result["region"] = region
    result["as_of"] = pd.to_datetime(df.index[-1]).strftime("%Y-%m-%d")
    result["valuation"] = fund
    result["sentiment"] = sent
    result["disclosures"] = dart.get_disclosures(code)
    result["disclaimer"] = (
        "이 예측은 과거 데이터로 학습한 통계 모델의 출력일 뿐이며, "
        "실제 투자 수익을 보장하지 않습니다. 단기 주가 예측의 정확도는 "
        "원리적으로 50%대에 머무릅니다. 학습/연구 목적으로만 사용하세요."
    )
    return result


@app.get("/api/prices")
def prices(codes: str):
    """보유 종목 평가용 현재가 일괄 조회 (codes=AAPL,005930)."""
    out = {}
    for code in [c.strip() for c in codes.split(",") if c.strip()]:
        try:
            df = data.get_ohlcv(code)
            out[code] = {
                "price": float(df["Close"].iloc[-1]),
                "name": data.get_name(code),
                "region": data.get_region(code),
                "as_of": pd.to_datetime(df.index[-1]).strftime("%Y-%m-%d"),
            }
        except Exception:
            out[code] = None
    return {"prices": out}


@app.get("/api/recommendations")
def recommendations():
    """오늘의 추천 (배치가 미리 계산해 저장한 결과를 읽기만 함)."""
    path = Path(__file__).resolve().parent / "recommendations.json"
    if not path.exists():
        return {"date": None, "buys": [],
                "message": "아직 추천이 생성되지 않았습니다. (배치 미실행)"}
    return json.loads(path.read_text(encoding="utf-8"))


_WATCH_FILE = Path(__file__).resolve().parent / "watch.json"


class WatchReq(BaseModel):
    codes: list[str]


@app.post("/api/watch")
def set_watch(req: WatchReq):
    """실시간 알림 워커가 감시할 종목(관심·보유) 동기화."""
    codes = sorted({c.strip() for c in req.codes if c.strip()})
    _WATCH_FILE.write_text(
        json.dumps({"codes": codes}, ensure_ascii=False), encoding="utf-8"
    )
    return {"ok": True, "count": len(codes)}


@app.get("/api/watch")
def get_watch():
    try:
        return json.loads(_WATCH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"codes": []}


@app.get("/")
def root():
    return {"status": "ok", "service": "StockView API"}
