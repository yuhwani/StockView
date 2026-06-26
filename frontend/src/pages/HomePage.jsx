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
        <div className="home-hero">
          <h2>💰 우리 가족 부자되자</h2>
          <p>
            한국·미국 주식을 ML·기술적 지표·실시간 이벤트로 분석해
            <b> 매수·관망·매도 판단</b>을 도와드려요. 종목을 검색하거나 아래 목록에서 골라보세요.
          </p>
          <div className="hero-tags">
            <span className="hero-tag">🤖 AI 종합 분석</span>
            <span className="hero-tag">📊 매수/관망/매도 신호</span>
            <span className="hero-tag">🔔 실시간 알림</span>
            <span className="hero-tag">🔥 오늘의 추천</span>
          </div>
        </div>
        <SearchBar onSelect={go} />
        <StockLists onSelectStock={go} watchlist={watchlist} />
      </div>

      <RecommendSidebar watchlist={watchlist} />
    </div>
  );
}
