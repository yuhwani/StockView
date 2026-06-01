import { useEffect, useRef, useState } from "react";
import { searchStocks } from "../api";

export default function SearchBar({ onSelect }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (query.trim().length < 1) {
      setResults([]);
      return;
    }
    // 디바운스: 입력이 멈춘 뒤 250ms 후 검색
    timer.current = setTimeout(async () => {
      try {
        const { results } = await searchStocks(query);
        setResults(results);
        setOpen(true);
      } catch {
        setResults([]);
      }
    }, 250);
    return () => clearTimeout(timer.current);
  }, [query]);

  const pick = (item) => {
    setQuery(`${item.Name} (${item.Code})`);
    setOpen(false);
    onSelect(item);
  };

  return (
    <div className="search">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        placeholder="종목명 또는 코드 검색 (예: 삼성전자, AAPL, 005930)"
      />
      {open && results.length > 0 && (
        <ul className="search-list">
          {results.map((r) => (
            <li key={r.Code} onClick={() => pick(r)}>
              <span className="s-name">
                {r.Region === "US" ? "🇺🇸" : "🇰🇷"} {r.Name}
              </span>
              <span className="s-meta">
                {r.Code} · {r.Market}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
