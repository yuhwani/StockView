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
  const [loading, setLoading] = useState(true);
  const [newsLoading, setNewsLoading] = useState(true);
  const [forecastLoading, setForecastLoading] = useState(true);
  const [btLoading, setBtLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async (refresh = false) => {
    setLoading(true);
    setError(null);
    if (!refresh) {
      setStock(null);
      setPrediction(null);
      setNews(null);
      setForecast(null);
      setBt(null);
    }

    setNewsLoading(true);
    getNews(code, refresh)
      .then((d) => setNews(d.items))
      .catch(() => setNews([]))
      .finally(() => setNewsLoading(false));

    // 미래 예측은 학습이 무거워 따로 (signal·차트 먼저 보이게)
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

    try {
      const [stockData, predData] = await Promise.all([
        getStock(code, refresh),
        predict(code, refresh),
      ]);
      setStock(stockData);
      setPrediction(predData);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  return (
    <div>
      <Link to="/home" className="back-link">
        ← 홈으로
      </Link>

      {loading && !stock && (
        <div className="loading">분석 중… (모델 학습에 몇 초 걸려요)</div>
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
              disabled={loading}
            >
              {loading ? "불러오는 중…" : "🔄 새로고침"}
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

      {prediction?.signal && (
        <SignalPanel
          signal={prediction.signal}
          levels={prediction.levels}
          valuation={prediction.valuation}
          region={prediction.region}
        />
      )}

      <div className="grid">
        {stock && <PriceChart candles={stock.candles} region={stock.region} />}
        {prediction && <PredictionPanel result={prediction} />}
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

      {stock && (
        <NewsPanel news={news} candles={stock.candles} loading={newsLoading} />
      )}
    </div>
  );
}
