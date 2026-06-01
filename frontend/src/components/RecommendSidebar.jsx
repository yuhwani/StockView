import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getRecommendations } from "../api";

// 홈 오른쪽에 고정(sticky)되는 컴팩트 오늘의 추천. 스크롤해도 따라온다.
export default function RecommendSidebar() {
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    getRecommendations()
      .then(setData)
      .catch(() => setData({ buys: [] }));
  }, []);

  const buys = (data?.buys || []).slice(0, 12);

  return (
    <aside className="rec-sidebar card">
      <div className="rec-side-head">
        <h3>🔥 오늘의 추천</h3>
        <Link to="/recommendations" className="rec-more">
          보러가기 →
        </Link>
      </div>
      {data?.date && <div className="rec-side-date">{data.date} 기준</div>}

      {buys.length === 0 ? (
        <div className="rec-side-empty">
          {data ? "아직 추천이 없어요." : "불러오는 중…"}
        </div>
      ) : (
        <ol className="rec-side-list">
          {buys.map((b) => (
            <li key={b.code} onClick={() => navigate(`/stock/${b.code}`)}>
              <span className="rsl-rank">{b.rank}</span>
              <span className="rsl-name">
                {b.region === "US" ? "🇺🇸" : "🇰🇷"} {b.name}
              </span>
              <span
                className={`rsl-ret ${b.ret20 > 0 ? "up" : b.ret20 < 0 ? "down" : ""}`}
              >
                {b.ret20 > 0 ? "+" : ""}
                {(b.ret20 * 100).toFixed(0)}%
              </span>
              <span className="rsl-score">{b.score}</span>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}
