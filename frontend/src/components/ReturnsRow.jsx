// 기간별 등락률 (1일·1주·1개월·3개월·1년) — 보유 중인 일봉으로 계산
const PERIODS = [
  { label: "1일", days: 1 },
  { label: "1주", days: 5 },
  { label: "1개월", days: 20 },
  { label: "3개월", days: 60 },
  { label: "1년", days: 252 },
];

function periodReturn(candles, n) {
  if (!candles || candles.length <= n) return null;
  const last = candles[candles.length - 1].Close;
  const prev = candles[candles.length - 1 - n].Close;
  if (!prev) return null;
  return last / prev - 1;
}

export default function ReturnsRow({ candles }) {
  if (!candles?.length) return null;
  return (
    <div className="returns-row">
      {PERIODS.map((p) => {
        const r = periodReturn(candles, p.days);
        const cls = r == null ? "" : r > 0 ? "up" : r < 0 ? "down" : "";
        return (
          <div key={p.label} className={`ret-cell ${cls}`}>
            <span className="ret-label">{p.label}</span>
            <span className="ret-val">
              {r == null ? "-" : (r > 0 ? "+" : "") + (r * 100).toFixed(1) + "%"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
