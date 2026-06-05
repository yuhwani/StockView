import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar";
import StockLists from "../components/StockLists";
import RecommendSidebar from "../components/RecommendSidebar";
import { useWatchlist } from "../useWatchlist";

// 홈: 검색·목록(왼쪽) + 고정 추천(오른쪽). 계정은 헤더에서 전환.
export default function HomePage() {
  const navigate = useNavigate();
  const watchlist = useWatchlist();
  const go = (item) => navigate(`/stock/${item.Code}`);

  return (
    <div className="home-layout">
      <div className="home-main">
        <SearchBar onSelect={go} />
        <StockLists onSelectStock={go} watchlist={watchlist} />
      </div>

      <RecommendSidebar watchlist={watchlist} />
    </div>
  );
}
