import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getPrices, preview } from "../api";
import { useWatchlist } from "../useWatchlist";
import { useAccounts } from "../AccountsContext";

function fmtPrice(v, region) {
  if (v == null) return "-";
  return region === "US"
    ? "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : Math.round(v).toLocaleString() + "원";
}

// 계정별 관심종목만 모아 보는 전용 페이지 (/watchlist)
export default function WatchlistPage() {
  const navigate = useNavigate();
  const { active } = useAccounts();
  const { items, isFav, toggle } = useWatchlist();
  const [prices, setPrices] = useState({});
  const [previews, setPreviews] = useState({});
  const [loading, setLoading] = useState(false);

  const codeKey = items.map((i) => i.Code).join(",");

  useEffect(() => {
    if (!codeKey) {
      setPrices({});
      return;
    }
    setLoading(true);
    getPrices(codeKey.split(","))
      .then((d) => setPrices(d.prices || {}))
      .catch(() => setPrices({}))
      .finally(() => setLoading(false));
  }, [codeKey]);

  const runPreview = async (code) => {
    setPreviews((p) => ({ ...p, [code]: { loading: true } }));
    try {
      const { prediction } = await preview(code);
      setPreviews((p) => ({
        ...p,
        [code]: {
          loading: false,
          dir: prediction.direction,
          prob: prediction.probability_up,
        },
      }));
    } catch {
      setPreviews((p) => ({ ...p, [code]: { loading: false, error: true } }));
    }
  };

  const previewAll = async () => {
    for (const it of items) {
      if (!previews[it.Code]) await runPreview(it.Code);
    }
  };

  return (
    <div className="watch-page">
      <Link to="/home" className="back-link">← 홈으로</Link>

      <div className="card list-card">
        <div className="list-head">
          <h3>⭐ 관심종목 {items.length > 0 && `(${items.length})`}</h3>
          <span className="list-desc">📁 {active?.name || "내 계좌"} 계정</span>
          {items.length > 0 && (
            <button className="mini-btn" onClick={previewAll}>⚡ 전체 예측</button>
          )}
        </div>

        {items.length === 0 ? (
          <div className="list-loading">
            아직 관심종목이 없어요. 종목·목록·추천에서 <b>☆</b> 를 눌러 추가하세요.
            <div className="rec-hint" style={{ marginTop: 8 }}>
              관심종목은 <b>계정마다 따로</b> 저장돼요. (계정 전환 시 그 계정 목록만 보임)
            </div>
          </div>
        ) : (
          <div className="list-table-wrap">
            <table className="list-table">
              <thead>
                <tr>
                  <th className="star-col">★</th>
                  <th>종목</th>
                  <th className="num">현재가</th>
                  <th className="num">전날대비</th>
                  <th className="num">예측</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => {
                  const px = prices[it.Code];
                  const pv = previews[it.Code];
                  const chg = px?.change;
                  return (
                    <tr key={it.Code} className="row">
                      <td className="star-col">
                        <button
                          className={`star-btn ${isFav(it.Code) ? "on" : ""}`}
                          onClick={() => toggle(it)}
                          title="관심종목에서 제거"
                        >
                          {isFav(it.Code) ? "★" : "☆"}
                        </button>
                      </td>
                      <td onClick={() => navigate(`/stock/${it.Code}`)} className="clk">
                        <span className="row-flag">{it.Region === "US" ? "🇺🇸" : "🇰🇷"}</span>
                        <span className="row-name">{it.Name}</span>
                        <span className="row-code">{it.Code}</span>
                      </td>
                      <td className="num">
                        {loading && !px ? "…" : fmtPrice(px?.price, it.Region)}
                      </td>
                      <td className={`num ${chg > 0 ? "up" : chg < 0 ? "down" : ""}`}>
                        {chg == null ? "-" : (chg > 0 ? "+" : "") + chg.toFixed(2) + "%"}
                      </td>
                      <td className="num pred-cell">
                        {!pv ? (
                          <button className="mini-btn ghost" onClick={() => runPreview(it.Code)}>
                            예측
                          </button>
                        ) : pv.loading ? (
                          <span className="pv-loading">…</span>
                        ) : pv.error ? (
                          <span className="pv-err">실패</span>
                        ) : (
                          <span className={`pv-badge ${pv.dir === "상승" ? "up" : "down"}`}>
                            {pv.dir === "상승" ? "▲" : "▼"}{" "}
                            {((pv.dir === "상승" ? pv.prob : 1 - pv.prob) * 100).toFixed(0)}%
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
