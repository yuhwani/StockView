import { useEffect, useState } from "react";
import { getRecommendations } from "../api";

// 오늘의 추천 — 배치가 미리 계산한 순위를 읽어 보여준다.
export default function RecommendPanel({ onSelectStock }) {
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
              <div className="rec-metrics">
                <span className="rec-score">{b.score}점</span>
                <span
                  className={`rec-ret ${b.ret20 > 0 ? "up" : b.ret20 < 0 ? "down" : ""}`}
                >
                  20일 {b.ret20 > 0 ? "+" : ""}
                  {(b.ret20 * 100).toFixed(1)}%
                </span>
              </div>
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
