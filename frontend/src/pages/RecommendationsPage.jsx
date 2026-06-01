import { useNavigate, Link } from "react-router-dom";
import RecommendPanel from "../components/RecommendPanel";

// 오늘의 추천 전체 현황 페이지 (/recommendations)
export default function RecommendationsPage() {
  const navigate = useNavigate();
  return (
    <div>
      <Link to="/" className="back-link">
        ← 홈으로
      </Link>
      <RecommendPanel onSelectStock={(item) => navigate(`/stock/${item.Code}`)} />
    </div>
  );
}
