import { useEffect, useState } from "react";
import { getLists, getList, preview } from "../api";

// ── 포맷 헬퍼 (행의 Region 기준) ───────────────────────────────
function fmtPrice(v, region) {
  if (v == null) return "-";
  return region === "US"
    ? "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : v.toLocaleString() + "원";
}
function fmtCap(v, region) {
  if (v == null) return "-";
  if (region === "US") {
    if (v >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
    if (v >= 1e9) return "$" + (v / 1e9).toFixed(1) + "B";
    if (v >= 1e6) return "$" + (v / 1e6).toFixed(0) + "M";
    return "$" + v.toLocaleString();
  }
  if (v >= 1e12) return (v / 1e12).toFixed(1) + "조";
  if (v >= 1e8) return (v / 1e8).toFixed(0) + "억";
  return v.toLocaleString();
}

const WATCH_ID = "__watchlist__";

export default function StockLists({ onSelectStock, watchlist }) {
  const { items: favItems, isFav, toggle } = watchlist;
  const [catalog, setCatalog] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [previews, setPreviews] = useState({}); // code -> {loading, dir, prob}

  useEffect(() => {
    getLists()
      .then((d) => {
        setCatalog(d.lists || []);
        // 홈이 비어 보이지 않게 기본 목록(한국 시총)을 자동으로 펼침
        const def =
          (d.lists || []).find((c) => c.id === "krx_cap100") || (d.lists || [])[0];
        if (def) openList(def.id);
      })
      .catch(() => setCatalog([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openList = async (id) => {
    if (activeId === id) {
      setActiveId(null);
      setItems([]);
      return;
    }
    setActiveId(id);
    if (id === WATCH_ID) {
      setItems(favItems);
      return;
    }
    setLoading(true);
    try {
      const { items } = await getList(id);
      setItems(items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  // 관심종목 탭이 열려있으면 즐겨찾기 변경을 실시간 반영
  useEffect(() => {
    if (activeId === WATCH_ID) setItems(favItems);
  }, [favItems, activeId]);

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

  // 상위 N개 순차 예측 (서버 과부하 방지로 하나씩)
  const previewTop = async (n) => {
    for (const it of items.slice(0, n)) {
      if (!previews[it.Code]) await runPreview(it.Code);
    }
  };

  const active =
    activeId === WATCH_ID
      ? { name: "관심종목", desc: "내가 저장한 종목", region: "MIX" }
      : catalog.find((c) => c.id === activeId);

  const hasMetrics = items.some((i) => i.Close != null);

  return (
    <div className="lists">
      <div className="list-chips">
        <button
          className={`chip star ${activeId === WATCH_ID ? "active" : ""}`}
          onClick={() => openList(WATCH_ID)}
        >
          ⭐ 관심종목 {favItems.length > 0 && `(${favItems.length})`}
        </button>
        {catalog.map((c) => (
          <button
            key={c.id}
            className={`chip ${activeId === c.id ? "active" : ""}`}
            onClick={() => openList(c.id)}
            title={c.desc}
          >
            {c.region === "US" ? "🇺🇸" : "🇰🇷"} {c.name}
          </button>
        ))}
      </div>

      {activeId && (
        <div className="card list-card">
          <div className="list-head">
            <h3>{active?.name}</h3>
            <span className="list-desc">{active?.desc}</span>
            {items.length > 0 && (
              <button className="mini-btn" onClick={() => previewTop(20)}>
                ⚡ 상위 20개 예측
              </button>
            )}
          </div>

          {loading ? (
            <div className="list-loading">불러오는 중…</div>
          ) : items.length === 0 ? (
            <div className="list-loading">
              {activeId === WATCH_ID
                ? "아직 관심종목이 없어요. 종목 옆 ☆ 를 눌러 추가하세요."
                : "데이터가 없습니다."}
            </div>
          ) : (
            <div className="list-table-wrap">
              <table className="list-table">
                <thead>
                  <tr>
                    <th className="star-col">★</th>
                    <th className="rank">#</th>
                    <th>종목</th>
                    {hasMetrics && <th className="num">현재가</th>}
                    {hasMetrics && <th className="num">전날대비</th>}
                    {hasMetrics && <th className="num">시총</th>}
                    <th className="num">예측</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, i) => {
                    const pv = previews[it.Code];
                    return (
                      <tr key={it.Code} className="row">
                        <td className="star-col">
                          <button
                            className={`star-btn ${isFav(it.Code) ? "on" : ""}`}
                            onClick={() => toggle(it)}
                            title={isFav(it.Code) ? "관심종목 제거" : "관심종목 추가"}
                          >
                            {isFav(it.Code) ? "★" : "☆"}
                          </button>
                        </td>
                        <td className="rank">{i + 1}</td>
                        <td onClick={() => onSelectStock(it)} className="clk">
                          <span className="row-flag">
                            {it.Region === "US" ? "🇺🇸" : "🇰🇷"}
                          </span>
                          <span className="row-name">{it.Name}</span>
                          <span className="row-code">{it.Code}</span>
                        </td>
                        {hasMetrics && (
                          <td className="num">{fmtPrice(it.Close, it.Region)}</td>
                        )}
                        {hasMetrics && (
                          <td
                            className={`num ${
                              it.ChangeRatio > 0
                                ? "up"
                                : it.ChangeRatio < 0
                                ? "down"
                                : ""
                            }`}
                          >
                            {it.ChangeRatio != null
                              ? (it.ChangeRatio > 0 ? "+" : "") +
                                it.ChangeRatio.toFixed(2) +
                                "%"
                              : "-"}
                          </td>
                        )}
                        {hasMetrics && (
                          <td className="num">{fmtCap(it.Marcap, it.Region)}</td>
                        )}
                        <td className="num pred-cell">
                          {!pv ? (
                            <button
                              className="mini-btn ghost"
                              onClick={() => runPreview(it.Code)}
                            >
                              예측
                            </button>
                          ) : pv.loading ? (
                            <span className="pv-loading">…</span>
                          ) : pv.error ? (
                            <span className="pv-err">실패</span>
                          ) : (
                            <span
                              className={`pv-badge ${
                                pv.dir === "상승" ? "up" : "down"
                              }`}
                              title={`${pv.dir}확률 ${(
                                (pv.dir === "상승" ? pv.prob : 1 - pv.prob) * 100
                              ).toFixed(0)}%`}
                            >
                              {pv.dir === "상승" ? "▲" : "▼"}{" "}
                              {(
                                (pv.dir === "상승" ? pv.prob : 1 - pv.prob) * 100
                              ).toFixed(0)}
                              %
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
      )}
    </div>
  );
}
