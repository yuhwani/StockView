import { useEffect } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Outlet,
  Link,
  Navigate,
  useNavigate,
} from "react-router-dom";
import HomePage from "./pages/HomePage";
import StockPage from "./pages/StockPage";
import RecommendationsPage from "./pages/RecommendationsPage";
import PortfolioPage from "./pages/PortfolioPage";
import SettingsPage from "./pages/SettingsPage";
import WatchlistPage from "./pages/WatchlistPage";
import AccountsPage from "./pages/AccountsPage";
import { AccountsProvider, useAccounts } from "./useAccounts";
import { useWatchlist } from "./useWatchlist";
import { syncWatch } from "./api";

// 관심·보유 종목을 백엔드(알림 워커)로 동기화
function WatchSync() {
  const { items } = useWatchlist();
  const { accounts, txOf } = useAccounts();
  const codes = [
    ...new Set([
      ...items.map((i) => i.Code),
      ...accounts.flatMap((a) => (txOf(a.id) || []).map((t) => t.code)),
    ]),
  ];
  const key = codes.join(",");
  useEffect(() => {
    if (codes.length) syncWatch(codes).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return null;
}

// 계정이 선택돼야 들어갈 수 있는 레이아웃 (없으면 계정 선택 화면으로)
function GatedLayout() {
  const { active } = useAccounts();
  const navigate = useNavigate();

  if (!active) return <Navigate to="/" replace />;

  return (
    <div className="app">
      <WatchSync />
      <header>
        <div className="header-top">
          <Link to="/home" className="logo-link">
            <h1>
              📈 StockView <span>투자 판단 도우미</span>
            </h1>
          </Link>
          <div className="header-acc">
            <span className="ha-name">📁 {active.name}</span>
            <Link to="/watchlist" className="mini-btn ghost">
              ⭐ 관심
            </Link>
            <Link to="/portfolio" className="mini-btn ghost">
              손익
            </Link>
            <Link to="/settings" className="mini-btn ghost">
              🔔 알림
            </Link>
            <button
              className="mini-btn ghost"
              onClick={() => navigate("/")}
            >
              계정 전환
            </button>
          </div>
        </div>
        <p className="sub">
          한국·미국 주식을 ML·기술적 지표로 분석해 매수·관망·매도 판단을 돕는 도구
        </p>
      </header>

      <Outlet />

      <footer>
        신호는 참고용입니다. 예측은 틀릴 수 있으며, 최종 투자 판단과 책임은 본인에게 있습니다.
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AccountsProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AccountsPage />} />
          <Route element={<GatedLayout />}>
            <Route path="/home" element={<HomePage />} />
            <Route path="/stock/:code" element={<StockPage />} />
            <Route path="/recommendations" element={<RecommendationsPage />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AccountsProvider>
  );
}
