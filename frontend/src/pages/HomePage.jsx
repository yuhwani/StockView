import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar";
import StockLists from "../components/StockLists";
import RecommendSidebar from "../components/RecommendSidebar";
import { useWatchlist } from "../useWatchlist";

// 홈: 왼쪽 = 검색·목록, 오른쪽 = 고정되는 오늘의 추천 사이드바
export default function HomePage() {
  const navigate = useNavigate();
  const watchlist = useWatchlist();
  const go = (item) => navigate(`/stock/${item.Code}`);

  return (
    <div className="home-layout">
      <div className="home-main">
        <SearchBar onSelect={go} />
        <StockLists onSelectStock={go} watchlist={watchlist} />
        <div className="empty">
          <p>
            종목을 검색하거나 위 목록에서 골라보세요. 🇰🇷 <b>삼성전자</b>,{" "}
            <b>005930</b> · 🇺🇸 <b>AAPL</b>, <b>Tesla</b>, <b>NVDA</b>
          </p>
        </div>
      </div>

      <RecommendSidebar />
    </div>
  );
}
