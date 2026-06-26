import { useEffect } from "react";
import { useAccounts } from "./AccountsContext";

// 계정별 관심종목 훅 — 저장/토글은 AccountsContext(watch)가 담당, 여기선 활성 계정 슬라이스만 제공
export function useWatchlist() {
  const { activeId, favsOf, toggleFav } = useAccounts();
  const id = activeId || "_global";
  const items = favsOf(id);

  // 예전 전역 즐겨찾기(stockview.watchlist)를 현재 계정으로 1회 이전
  useEffect(() => {
    const raw = localStorage.getItem("stockview.watchlist");
    if (raw == null) return;
    try {
      const arr = JSON.parse(raw) || [];
      arr.forEach((s) => {
        if (!favsOf(id).some((i) => i.Code === s.Code)) toggleFav(id, s);
      });
    } catch {
      /* ignore */
    }
    localStorage.removeItem("stockview.watchlist");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isFav = (code) => items.some((i) => i.Code === code);
  const toggle = (stock) => toggleFav(id, stock);

  return { items, isFav, toggle };
}
