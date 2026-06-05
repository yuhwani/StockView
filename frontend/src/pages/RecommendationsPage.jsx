import { useNavigate, Link } from "react-router-dom";
import RecommendPanel from "../components/RecommendPanel";
import { useWatchlist } from "../useWatchlist";

// 오늘의 추천 전체 현황 페이지 (/recommendations)
export default function RecommendationsPage() {
  const navigate = useNavigate();
  const watchlist = useWatchlist();
  return (
    <div>
      <Link to="/home" className="back-link">
        ← 홈으로
      </Link>
      <RecommendPanel
        onSelectStock={(item) => navigate(`/stock/${item.Code}`)}
        watchlist={watchlist}
      />
    </div>
  );
}
