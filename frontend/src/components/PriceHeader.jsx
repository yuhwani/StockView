// 현재 주가 + 전일대비, 그리고 1일전·7일전·한달전 주가
function fmt(v, region) {
  if (v == null) return "-";
  return region === "US"
    ? "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : Math.round(v).toLocaleString() + "원";
}

// N일(달력일) 전 시점의 종가 — 그 날짜 이하인 가장 최근 거래일을 찾는다.
function priceDaysAgo(candles, n) {
  const last = candles[candles.length - 1];
  const target = new Date(last.Date);
  target.setDate(target.getDate() - n);
  for (let i = candles.length - 2; i >= 0; i--) {
    if (new Date(candles[i].Date) <= target) return candles[i];
  }
  return null;
}

const PAST = [
  { label: "1일 전", days: 1 },
  { label: "7일 전", days: 7 },
  { label: "한달 전", days: 30 },
];

export default function PriceHeader({ candles, region }) {
  if (!candles?.length) return null;
  const last = candles[candles.length - 1].Close;
  const prev = candles.length > 1 ? candles[candles.length - 2].Close : null;
  const diff = prev != null ? last - prev : null;
  const pct = prev ? (last / prev - 1) * 100 : null;
  const up = diff != null && diff > 0;
  const down = diff != null && diff < 0;
  const cls = up ? "up" : down ? "down" : "";

  return (
    <div className="price-block">
      <div className="price-header">
        <span className="ph-price">{fmt(last, region)}</span>
        {diff != null && (
          <span className={`ph-change ${cls}`}>
            {up ? "▲" : down ? "▼" : ""}{" "}
            {fmt(Math.abs(diff), region)} ({pct > 0 ? "+" : ""}
            {pct.toFixed(2)}%)
          </span>
        )}
        <span className="ph-sub">전일대비</span>
      </div>

      <div className="past-prices">
        {PAST.map((p) => {
          const c = priceDaysAgo(candles, p.days);
          return (
            <div key={p.label} className="pp-cell">
              <span className="pp-label">{p.label}</span>
              <span className="pp-price">{c ? fmt(c.Close, region) : "-"}</span>
              {c && <span className="pp-date">{c.Date}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
