import { useCallback, useEffect, useState } from "react";

const KEY = "stockview.watchlist";

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || [];
  } catch {
    return [];
  }
}

// 관심종목을 localStorage에 저장/관리하는 훅
export function useWatchlist() {
  const [items, setItems] = useState(load);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(items));
  }, [items]);

  const isFav = useCallback(
    (code) => items.some((i) => i.Code === code),
    [items]
  );

  const toggle = useCallback((stock) => {
    // 목록/상세 어디서 와도 최소 필드만 표준화해서 저장
    const entry = {
      Code: stock.Code || stock.code,
      Name: stock.Name || stock.name,
      Region: stock.Region || stock.region || "KR",
      Market: stock.Market || stock.market || "",
    };
    setItems((prev) =>
      prev.some((i) => i.Code === entry.Code)
        ? prev.filter((i) => i.Code !== entry.Code)
        : [...prev, entry]
    );
  }, []);

  return { items, isFav, toggle };
}
