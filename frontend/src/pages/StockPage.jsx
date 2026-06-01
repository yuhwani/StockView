import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import PriceChart from "../components/PriceChart";
import PredictionPanel from "../components/PredictionPanel";
import SignalPanel from "../components/SignalPanel";
import NewsPanel from "../components/NewsPanel";
import ReturnsRow from "../components/ReturnsRow";
import { getStock, predict, getNews } from "../api";
import { useWatchlist } from "../useWatchlist";

// 종목 상세 분석 페이지 — URL의 :code 로 데이터를 받아 분석을 보여준다.
export default function StockPage() {
  const { code } = useParams();
  const watchlist = useWatchlist();
  const [stock, setStock] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [news, setNews] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newsLoading, setNewsLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async (refresh = false) => {
    setLoading(true);
    setError(null);
    if (!refresh) {
      setStock(null);
      setPrediction(null);
      setNews(null);
    }

    setNewsLoading(true);
    getNews(code, refresh)
      .then((d) => setNews(d.items))
      .catch(() => setNews([]))
      .finally(() => setNewsLoading(false));

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
      <Link to="/" className="back-link">
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

      {stock && <ReturnsRow candles={stock.candles} />}

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
        <NewsPanel news={news} candles={stock.candles} loading={newsLoading} />
      )}
    </div>
  );
}
