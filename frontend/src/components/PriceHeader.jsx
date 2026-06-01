// 현재 주가 표시 (전일대비 변동 포함) — 보유 일봉의 마지막 종가 기준
function fmt(v, region) {
  if (v == null) return "-";
  return region === "US"
    ? "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : Math.round(v).toLocaleString() + "원";
}

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
  );
}
