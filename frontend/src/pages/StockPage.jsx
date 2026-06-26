import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import PriceChart from "../components/PriceChart";
import PredictionPanel from "../components/PredictionPanel";
import SignalPanel from "../components/SignalPanel";
import NewsPanel from "../components/NewsPanel";
import PriceHeader from "../components/PriceHeader";
import ForecastPanel from "../components/ForecastPanel";
import BacktestPanel from "../components/BacktestPanel";
import DisclosurePanel from "../components/DisclosurePanel";
import AISummaryPanel from "../components/AISummaryPanel";
import TradePanel from "../components/TradePanel";
import { getStock, predict, getNews, getForecast, getBacktest } from "../api";
import { useWatchlist } from "../useWatchlist";
import { useAccounts } from "../useAccounts";
import { heldQtyOf } from "../portfolio";

// 종목 상세 분석 페이지 — URL의 :code 로 데이터를 받아 분석을 보여준다.
export default function StockPage() {
  const { code } = useParams();
  const watchlist = useWatchlist();
  const accounts = useAccounts();
  const [stock, setStock] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [news, setNews] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [bt, setBt] = useState(null);
  const [stockLoading, setStockLoading] = useState(true);
  const [predLoading, setPredLoading] = useState(true);
  const [newsLoading, setNewsLoading] = useState(true);
  const [forecastLoading, setForecastLoading] = useState(true);
  const [btLoading, setBtLoading] = useState(true);
  const [error, setError] = useState(null);

  // 각 데이터를 '독립적으로' 받아 먼저 끝난 것부터 보여준다 (학습 기다리지 않고)
  const load = (refresh = false) => {
    setError(null);
    if (!refresh) {
      setStock(null);
      setPrediction(null);
      setNews(null);
      setForecast(null);
      setBt(null);
    }

    // 1) 시세 — 가볍고 빠름 → 차트·매매·헤더가 즉시 뜸
    setStockLoading(true);
    getStock(code, refresh)
      .then(setStock)
      .catch((e) => setError(e.message))
      .finally(() => setStockLoading(false));

    // 2) 종합 신호·예측 — 모델 학습이라 무거움 → 따로 (다른 건 그동안 봄)
    setPredLoading(true);
    predict(code, refresh)
      .then(setPrediction)
      .catch(() => setPrediction(null))
      .finally(() => setPredLoading(false));

    setNewsLoading(true);
    getNews(code, refresh)
      .then((d) => setNews(d.items))
      .catch(() => setNews([]))
      .finally(() => setNewsLoading(false));

    setForecastLoading(true);
    getForecast(code, refresh)
      .then(setForecast)
      .catch(() => setForecast({ horizons: [] }))
      .finally(() => setForecastLoading(false));

    setBtLoading(true);
    getBacktest(code, refresh)
      .then(setBt)
      .catch(() => setBt({ curve: [] }))
      .finally(() => setBtLoading(false));
  };

  const busy = stockLoading || predLoading;

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  return (
    <div>
      <Link to="/home" className="back-link">
        ← 홈으로
      </Link>

      {stockLoading && !stock && (
        <div className="loading-inline">⏳ 시세 불러오는 중…</div>
      )}
      {error && <div className="error">⚠️ {error}</div>}

      {stock && (
        <div className="title-row">
          <h2>
            {stock.region === "US" ? "🇺🇸" : "🇰🇷"} {stock.name}{" "}
            <span className="code">{stock.code}</span>
            <button
              className={`star-btn big ${watchlist.isFav(stock.code) ? "on" : ""}`}
              onClick={() => watchlist.toggle(stock)}
              title="관심종목"
            >
              {watchlist.isFav(stock.code) ? "★" : "☆"}
            </button>
          </h2>
          <div className="asof-row">
            <span className="asof">
              📅 기준: {stock.as_of} 종가 · 일봉 데이터 (실시간 아님)
            </span>
            <button
              className="refresh-btn"
              onClick={() => load(true)}
              disabled={busy}
            >
              {busy ? "불러오는 중…" : "🔄 새로고침"}
            </button>
          </div>
        </div>
      )}

      {stock && <PriceHeader candles={stock.candles} region={stock.region} />}

      {stock && (
        <TradePanel
          account={accounts.active}
          stock={stock}
          currentPrice={stock.candles[stock.candles.length - 1].Close}
          heldQty={
            accounts.activeId
              ? heldQtyOf(accounts.txOf(accounts.activeId), stock.code)
              : 0
          }
          onTrade={(t) => accounts.addTrade(accounts.activeId, t)}
        />
      )}

      {prediction?.signal ? (
        <SignalPanel
          signal={prediction.signal}
          levels={prediction.levels}
          valuation={prediction.valuation}
          region={prediction.region}
        />
      ) : (
        stock && predLoading && (
          <div className="panel-loading">
            🧭 종합 매수/매도 신호 분석 중… <small>(모델 학습 중이라 잠깐 걸려요 — 아래 차트·뉴스는 먼저 보세요)</small>
          </div>
        )
      )}

      <div className="grid">
        {stock && <PriceChart candles={stock.candles} region={stock.region} />}
        {prediction ? (
          <PredictionPanel result={prediction} />
        ) : (
          stock && predLoading && (
            <div className="card panel-loading">📈 다음날 예측 학습 중…</div>
          )
        )}
      </div>

      {stock && (
        <ForecastPanel
          forecast={forecast}
          region={stock.region}
          loading={forecastLoading}
        />
      )}

      {stock && <BacktestPanel backtest={bt} loading={btLoading} />}

      {prediction?.disclosures?.length > 0 && (
        <DisclosurePanel disclosures={prediction.disclosures} />
      )}

      {stock && <AISummaryPanel code={stock.code} />}

      {stock && (
        <NewsPanel news={news} candles={stock.candles} loading={newsLoading} />
      )}
    </div>
  );
}
