import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getRecommendations } from "../api";

// 홈 오른쪽에 고정(sticky)되는 컴팩트 오늘의 추천. 스크롤해도 따라온다.
export default function RecommendSidebar({ watchlist }) {
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
              <div className="rsl-top">
                <span className="rsl-rank">{b.rank}</span>
                <span className="rsl-name">
                  {b.region === "US" ? "🇺🇸" : "🇰🇷"} {b.name}
                </span>
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
              <div className="rsl-rets">
                <SideRet label="전날" v={b.ret1} />
                <SideRet label="1주" v={b.ret5} />
                <SideRet label="2주" v={b.ret10} />
                <SideRet label="한달" v={b.ret20} />
              </div>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

function SideRet({ label, v }) {
  const cls = v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
  return (
    <span className={`sr ${cls}`}>
      <span className="sr-label">{label}</span>
      <span className="sr-val">
        {v == null ? "-" : (v > 0 ? "+" : "") + (v * 100).toFixed(1) + "%"}
      </span>
    </span>
  );
}
