import { useEffect, useState } from "react";
import { getRecommendations } from "../api";

// 오늘의 추천 — 배치가 미리 계산한 순위를 읽어 보여준다.
export default function RecommendPanel({ onSelectStock, watchlist }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRecommendations()
      .then(setData)
      .catch(() => setData({ buys: [] }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="card rec-card">추천 불러오는 중…</div>;

  const buys = data?.buys || [];

  return (
    <div className="card rec-card">
      <div className="rec-head">
        <h3>🔥 오늘의 추천</h3>
        {data?.date && (
          <span className="rec-date">
            {data.date} 기준 · {data.scored}개 종목 중 상위 {buys.length}
          </span>
        )}
      </div>

      {buys.length === 0 ? (
        <div className="rec-empty">
          {data?.message || "아직 추천이 없습니다."}
          <div className="rec-hint">
            터미널에서 <code>make recommend</code> 를 실행하면 생성됩니다.
            (매일 자동 실행도 설정됨)
          </div>
        </div>
      ) : (
        <div className="rec-list">
          {buys.map((b) => (
            <div
              key={b.code}
              className="rec-row"
              onClick={() => onSelectStock({ Code: b.code })}
            >
              <span className="rec-rank">{b.rank}</span>
              <div className="rec-main">
                <div className="rec-name">
                  {b.region === "US" ? "🇺🇸" : "🇰🇷"} {b.name}
                  <span className="rec-code">{b.code}</span>
                </div>
                <div className="rec-reasons">
                  {(b.reasons || []).slice(0, 2).join(" · ")}
                </div>
              </div>
              <div className="rec-rets">
                <Ret label="전날" v={b.ret1} />
                <Ret label="1주전" v={b.ret5} />
                <Ret label="2주전" v={b.ret10} />
                <Ret label="한달전" v={b.ret20} />
              </div>
              {watchlist && (
                <button
                  className={`star-btn ${watchlist.isFav(b.code) ? "on" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    watchlist.toggle(b);
                  }}
                  title={watchlist.isFav(b.code) ? "관심종목 제거" : "관심종목 추가"}
                >
                  {watchlist.isFav(b.code) ? "★" : "☆"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <p className="rec-note">
        가격 기반 기술적 점수(추세·모멘텀·거래량·신고가)로 매긴 순위입니다.
        클릭하면 ML·펀더멘털·뉴스까지 종합한 상세 판단을 볼 수 있어요. 참고용입니다.
      </p>
    </div>
  );
}

function Ret({ label, v }) {
  const cls = v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
  return (
    <span className={`rec-ret ${cls}`}>
      <span className="rr-label">{label}</span>
      {v == null ? "-" : (v > 0 ? "+" : "") + (v * 100).toFixed(1) + "%"}
    </span>
  );
}
