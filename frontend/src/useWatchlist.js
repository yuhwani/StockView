import { useCallback, useEffect, useState } from "react";
import { useAccounts } from "./AccountsContext";

// 계정별 즐겨찾기: { [accountId]: [entries] } 하나로 보관 (계정 전환 시 슬라이스만 교체)
const KEY = "stockview.watchlists";
const LEGACY = "stockview.watchlist"; // 예전 전역 단일 목록

function loadAll() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || {};
  } catch {
    return {};
  }
}

// 계정별 관심종목 훅 (활성 계정 기준)
export function useWatchlist() {
  const { activeId } = useAccounts();
  const id = activeId || "_global";
  const [all, setAll] = useState(loadAll);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(all));
  }, [all]);

  // 예전 전역 즐겨찾기를 현재 계정으로 1회 이전 (데이터 보존)
  useEffect(() => {
    const raw = localStorage.getItem(LEGACY);
    if (raw == null) return;
    try {
      const arr = JSON.parse(raw) || [];
      if (arr.length) {
        setAll((prev) => (prev[id]?.length ? prev : { ...prev, [id]: arr }));
      }
    } catch {
      /* ignore */
    }
    localStorage.removeItem(LEGACY);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const items = all[id] || [];

  const isFav = useCallback(
    (code) => (all[id] || []).some((i) => i.Code === code),
    [all, id]
  );

  const toggle = useCallback(
    (stock) => {
      const entry = {
        Code: stock.Code || stock.code,
        Name: stock.Name || stock.name,
        Region: stock.Region || stock.region || "KR",
        Market: stock.Market || stock.market || "",
      };
      setAll((prev) => {
        const list = prev[id] || [];
        const next = list.some((i) => i.Code === entry.Code)
          ? list.filter((i) => i.Code !== entry.Code)
          : [...list, entry];
        return { ...prev, [id]: next };
      });
    },
    [id]
  );

  return { items, isFav, toggle };
}
