import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar";
import StockLists from "../components/StockLists";
import RecommendSidebar from "../components/RecommendSidebar";
import AccountBar from "../components/AccountBar";
import { useWatchlist } from "../useWatchlist";
import { useAccounts } from "../useAccounts";

// 홈: 계정 바 + 검색·목록(왼쪽) + 고정 추천(오른쪽)
export default function HomePage() {
  const navigate = useNavigate();
  const watchlist = useWatchlist();
  const accounts = useAccounts();
  const go = (item) => navigate(`/stock/${item.Code}`);

  return (
    <>
      <AccountBar
        accounts={accounts.accounts}
        activeId={accounts.activeId}
        onSelect={accounts.selectAccount}
        onAdd={accounts.addAccount}
      />

      <div className="home-layout">
        <div className="home-main">
          <SearchBar onSelect={go} />
          <StockLists onSelectStock={go} watchlist={watchlist} />
        </div>

        <RecommendSidebar />
      </div>
    </>
  );
}
