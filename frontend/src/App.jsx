import { useState } from "react";
import SearchBar from "./components/SearchBar";
import StockLists from "./components/StockLists";
import PriceChart from "./components/PriceChart";
import PredictionPanel from "./components/PredictionPanel";
import SignalPanel from "./components/SignalPanel";
import NewsPanel from "./components/NewsPanel";
import { getStock, predict, getNews } from "./api";
import { useWatchlist } from "./useWatchlist";

export default function App() {
  const [stock, setStock] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [news, setNews] = useState(null);
  const [newsLoading, setNewsLoading] = useState(false);
  const watchlist = useWatchlist();

  const handleSelect = async (item) => {
    setLoading(true);
    setError(null);
    setPrediction(null);
    setStock(null);
    setNews(null);

    // 뉴스는 별도로 (실패해도 차트/예측은 보여야 하므로)
    setNewsLoading(true);
    getNews(item.Code)
      .then((d) => setNews(d.items))
      .catch(() => setNews([]))
      .finally(() => setNewsLoading(false));

    try {
      // 시세와 예측을 동시에 요청
      const [stockData, predData] = await Promise.all([
        getStock(item.Code),
        predict(item.Code),
      ]);
      setStock(stockData);
      setPrediction(predData);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header>
        <h1>
          📈 StockView <span>투자 판단 도우미</span>
        </h1>
        <p className="sub">
          한국·미국 주식을 ML·기술적 지표로 분석해 매수·관망·매도 판단을 돕는 도구
        </p>
      </header>

      <SearchBar onSelect={handleSelect} />

      <StockLists onSelectStock={handleSelect} watchlist={watchlist} />

      {loading && <div className="loading">분석 중… (모델 학습에 몇 초 걸려요)</div>}
      {error && <div className="error">⚠️ {error}</div>}

      {stock && (
        <div className="title-row">
          <h2>
            {stock.region === "US" ? "🇺🇸" : "🇰🇷"} {stock.name}{" "}
            <span className="code">{stock.code}</span>
            <button
              className={`star-btn big ${
                watchlist.isFav(stock.code) ? "on" : ""
              }`}
              onClick={() => watchlist.toggle(stock)}
              title="관심종목"
            >
              {watchlist.isFav(stock.code) ? "★" : "☆"}
            </button>
          </h2>
        </div>
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
        <NewsPanel
          news={news}
          candles={stock.candles}
          loading={newsLoading}
        />
      )}

      {!stock && !loading && (
        <div className="empty">
          <p>
            위에서 종목을 검색해 보세요. 🇰🇷 <b>삼성전자</b>, <b>005930</b> ·
            🇺🇸 <b>AAPL</b>, <b>Tesla</b>, <b>NVDA</b>
          </p>
        </div>
      )}

      <footer>
        신호는 참고용입니다. 예측은 틀릴 수 있으며, 최종 투자 판단과 책임은 본인에게 있습니다.
      </footer>
    </div>
  );
}
