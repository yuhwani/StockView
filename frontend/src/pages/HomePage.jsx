import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar";
import StockLists from "../components/StockLists";
import RecommendPanel from "../components/RecommendPanel";
import { useWatchlist } from "../useWatchlist";

// 홈: 검색 · 오늘의 추천 · 목록 · 관심종목
// 종목을 고르면 상세 페이지(/stock/:code)로 이동한다.
export default function HomePage() {
  const navigate = useNavigate();
  const watchlist = useWatchlist();
  const go = (item) => navigate(`/stock/${item.Code}`);

  return (
    <>
      <SearchBar onSelect={go} />
      <RecommendPanel onSelectStock={go} />
      <StockLists onSelectStock={go} watchlist={watchlist} />

      <div className="empty">
        <p>
          종목을 검색하거나 위 목록에서 골라보세요. 🇰🇷 <b>삼성전자</b>,{" "}
          <b>005930</b> · 🇺🇸 <b>AAPL</b>, <b>Tesla</b>, <b>NVDA</b>
        </p>
      </div>
    </>
  );
}
