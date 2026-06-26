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
import { syncWatch, syncAccounts } from "./api";
import { heldQtyOf } from "./portfolio";

// 계정별 즐겨찾기·보유를 백엔드(알림 워커)로 동기화 — 실시간 감시 + 계정별 보고서용
function WatchSync() {
  const { accounts, txOf, watch } = useAccounts();

  // 계정마다 {name, favorites, holdings(qty·avg 포함)} 구성
  const payload = accounts.map((a) => {
    const txs = txOf(a.id) || [];
    const codes = [...new Set(txs.map((t) => t.code))];
    const holdings = codes
      .filter((c) => heldQtyOf(txs, c) > 0)
      .map((c) => {
        const t = txs.find((x) => x.code === c) || {};
        // 평균단가 = 보유분 매입원가 / 수량
        let qty = 0, cost = 0;
        for (const x of txs.filter((x) => x.code === c)) {
          const q = Number(x.qty) || 0, p = Number(x.price) || 0;
          if (x.side === "buy") { qty += q; cost += q * p; }
          else { const avg = qty > 0 ? cost / qty : 0; const s = Math.min(q, qty); cost -= avg * s; qty -= s; }
        }
        return { code: c, name: t.name, region: t.region, qty, avg: qty > 0 ? cost / qty : 0 };
      });
    const favorites = (watch[a.id] || []).map((f) => ({
      code: f.Code, name: f.Name, region: f.Region,
    }));
    return { id: a.id, name: a.name, favorites, holdings };
  });

  const key = JSON.stringify(payload);
  useEffect(() => {
    if (!accounts.length) return;
    syncAccounts(payload).catch(() => {});
    // 실시간 워커용 평면 코드 목록(전 계정 합집합)도 유지
    const codes = [
      ...new Set(payload.flatMap((a) => [
        ...a.favorites.map((f) => f.code),
        ...a.holdings.map((h) => h.code),
      ])),
    ];
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
