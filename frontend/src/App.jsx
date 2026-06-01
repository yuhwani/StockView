import { BrowserRouter, Routes, Route, Outlet, Link } from "react-router-dom";
import HomePage from "./pages/HomePage";
import StockPage from "./pages/StockPage";
import RecommendationsPage from "./pages/RecommendationsPage";

// 공통 레이아웃 (헤더/푸터) — 로고를 누르면 홈으로
function Layout() {
  return (
    <div className="app">
      <header>
        <Link to="/" className="logo-link">
          <h1>
            📈 StockView <span>투자 판단 도우미</span>
          </h1>
        </Link>
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
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/stock/:code" element={<StockPage />} />
          <Route path="/recommendations" element={<RecommendationsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
