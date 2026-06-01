"""StockView 백엔드 API (FastAPI).

엔드포인트:
  GET /api/search?q=...          종목 검색
  GET /api/stock/{code}          OHLCV 시세 (차트용)
  GET /api/predict/{code}        ML 예측 + 백테스트 평가
"""
from __future__ import annotations

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import data
import model as ml
import news as news_mod

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
def stock(code: str, start: str = "2018-01-01"):
    try:
        df = data.get_ohlcv(code, start)
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
def news(code: str):
    """종목 관련 최근 뉴스 헤드라인 (한국=네이버, 미국=구글 뉴스)."""
    region = data.get_region(code)
    name = data.get_name(code) or code
    items = news_mod.get_news(code, region, name)
    return {"code": code, "region": region, "items": items}


@app.get("/api/predict/{code}")
def predict(code: str):
    try:
        df = data.get_ohlcv(code)
        result = ml.train_and_evaluate(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result["code"] = code
    result["name"] = data.get_name(code)
    result["region"] = data.get_region(code)
    result["disclaimer"] = (
        "이 예측은 과거 데이터로 학습한 통계 모델의 출력일 뿐이며, "
        "실제 투자 수익을 보장하지 않습니다. 단기 주가 예측의 정확도는 "
        "원리적으로 50%대에 머무릅니다. 학습/연구 목적으로만 사용하세요."
    )
    return result


@app.get("/")
def root():
    return {"status": "ok", "service": "StockView API"}
